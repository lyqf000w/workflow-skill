"""Local workflow inspection. No network access; raw prompts are not printed."""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
from typing import Any

META = {"id", "tenant_id", "app_id", "type", "version", "hash", "created_by", "updated_by",
        "created_at", "updated_at", "created_by_account", "updated_by_account", "marked_name", "marked_comment"}
UI_ONLY = {"selected", "_runningStatus", "_singleRunningStatus", "_isSingleRun",
           "_connectedNodeIsSelected", "_connectedNodeIsHovering"}
WRITABLE = {"graph", "features", "conversation_variables", "environment_variables",
            "application_variables", "reflection_learning"}
SELECTORS = {"variable_selector", "value_selector", "input_variable_selector", "assigned_variable_selector",
             "query_variable_selector", "output_selector", "iterator_selector", "dataset_variable_selector"}
SPECIAL = {"sys", "conversation", "application", "env", "environment"}
TEMPLATE = re.compile(r"\{\{#([^#{}]+)#\}\}")


def unwrap(value: Any) -> dict:
    for _ in range(5):
        if isinstance(value, dict) and isinstance(value.get("graph"), dict):
            if not isinstance(value["graph"].get("nodes"), list) or not isinstance(value["graph"].get("edges"), list):
                raise ValueError("graph.nodes and graph.edges must be arrays")
            return value
        if not isinstance(value, dict):
            break
        if isinstance(value.get("workflow"), dict):
            value = value["workflow"]
        elif isinstance(value.get("data"), dict):
            value = value["data"]
        else:
            break
    raise ValueError("No supported workflow graph found")


def read_document(path: str | Path) -> Any:
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError("YAML input requires PyYAML; JSON input uses only the standard library") from exc
        return yaml.safe_load(text)
    return json.loads(text)


def load_workflow(path: str | Path) -> dict:
    return unwrap(read_document(path))


def clean(value: Any) -> Any:
    """Copy configuration without dropping similarly named business parameters."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def configuration(value: dict) -> dict:
    w = unwrap(value)
    result = clean({k: v for k, v in w.items() if k not in META})
    # Only known canvas locations are cosmetic. A tool argument named "selected"
    # or a structured-output property with that name is business configuration.
    for collection in ("nodes", "edges"):
        for element in result["graph"][collection]:
            for key in UI_ONLY:
                element.pop(key, None)
            data = element.get("data")
            if isinstance(data, dict):
                for key in UI_ONLY - {"selected"}:
                    data.pop(key, None)
    return result


def fingerprint(value: dict) -> str:
    encoded = json.dumps(configuration(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def node_map(w: dict) -> dict[str, dict]:
    return {str(n["id"]): n for n in unwrap(w)["graph"]["nodes"]}


def summary(w: dict) -> dict:
    w = unwrap(w)
    return {"nodes": len(w["graph"]["nodes"]), "edges": len(w["graph"]["edges"]),
            "conversation_variables": len(w.get("conversation_variables") or []),
            "fingerprint": fingerprint(w), "hash": w.get("hash"), "updated_at": w.get("updated_at")}


def references(value: Any):
    if isinstance(value, str):
        for match in TEMPLATE.finditer(value):
            yield match.group(1).split(".")
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in SELECTORS and isinstance(child, list) and child and all(isinstance(x, str) for x in child):
                yield child
            elif key == "query" and isinstance(child, list) and len(child) >= 2 and all(isinstance(x, str) for x in child):
                yield child
            else:
                yield from references(child)
            # Aggregator input arrays and loop variable selectors.
            if key == "variables" and isinstance(child, list):
                for item in child:
                    if isinstance(item, list) and len(item) >= 2 and all(isinstance(x, str) for x in item):
                        yield item
            if key == "value" and value.get("value_type") == "variable" and isinstance(child, list):
                if child and all(isinstance(x, str) for x in child):
                    yield child


def audit(w: dict, max_path_nodes: int | None = None) -> dict:
    w = unwrap(w)
    if max_path_nodes is not None and max_path_nodes < 1:
        raise ValueError("Path limit must be positive when supplied")
    errors, warnings = [], []
    nodes, edges = w["graph"]["nodes"], w["graph"]["edges"]
    ids = [str(n.get("id", "")) for n in nodes]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        errors.append("missing_or_duplicate_node_id")
    edge_ids = [str(e.get("id", "")) for e in edges]
    if any(not x for x in edge_ids) or len(edge_ids) != len(set(edge_ids)):
        errors.append("missing_or_duplicate_edge_id")
    nm = {str(n.get("id", "")): n for n in nodes}
    for n in nodes:
        if not isinstance(n.get("id"), str):
            errors.append(f"node_id_not_string:{n.get('id')}")
        if not isinstance(n.get("data"), dict) or not n.get("data", {}).get("type"):
            errors.append(f"node_missing_type:{n.get('id')}")
    cv_names = [v.get("name", v.get("variable")) for v in w.get("conversation_variables") or []]
    if len(cv_names) != len(set(cv_names)):
        errors.append("duplicate_conversation_variable")
    cv = set(cv_names)
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree = {i: 0 for i in ids}
    out_handles: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        a, b = str(e.get("source", "")), str(e.get("target", ""))
        if a not in nm or b not in nm:
            errors.append(f"dangling_edge:{e.get('id')}")
            continue
        adjacency[a].append(b)
        indegree[b] += 1
        handle = str(e.get("sourceHandle") or "source")
        out_handles[a].add(handle)
        for key, node_id in [("sourceType", a), ("targetType", b)]:
            declared = (e.get("data") or {}).get(key)
            if declared and declared != nm[node_id].get("data", {}).get("type"):
                errors.append(f"edge_type_mismatch:{e.get('id')}:{key}")
        d = nm[a].get("data", {})
        if d.get("type") == "if-else":
            allowed = {str(c.get("case_id", c.get("id"))) for c in d.get("cases", [])} | {"false"}
            if not d.get("cases"):
                allowed.add("true")
            if handle not in allowed:
                errors.append(f"unknown_branch_handle:{a}:{handle}")
    titles = defaultdict(list)
    for i, n in nm.items():
        d = n.get("data", {})
        title = str(d.get("title") or "")
        titles[title].append(i)
        if not title:
            warnings.append(f"untitled_node:{i}")
        if not str(d.get("desc") or "").strip() and d.get("type") not in {"start", "loop-start", "iteration-start"}:
            warnings.append(f"missing_node_description:{i}")
        if d.get("type") == "if-else" and "false" not in out_handles[i]:
            warnings.append(f"unconnected_else_branch:{i}")
        if n.get("parentId") and str(n["parentId"]) not in nm:
            errors.append(f"missing_container:{i}")
        for ref in references(d):
            if len(ref) < 2:
                continue
            source, field = ref[0], ref[1]
            if source not in SPECIAL and source not in nm:
                errors.append(f"missing_reference:{i}:{source}.{field}")
            elif source == "conversation" and field not in cv:
                errors.append(f"missing_conversation_variable:{i}:{field}")
            elif source in nm and nm[source].get("data", {}).get("type") == "param-parse":
                outputs = {o.get("name") for o in nm[source]["data"].get("outputs") or []}
                if field not in outputs:
                    errors.append(f"missing_parser_output:{i}:{source}.{field}")
    for title, members in titles.items():
        if title and len(members) > 1:
            warnings.append("duplicate_display_title:" + ",".join(members))
    queue = deque(i for i, degree in indegree.items() if degree == 0)
    remaining = dict(indegree)
    order = []
    while queue:
        a = queue.popleft()
        order.append(a)
        for b in adjacency[a]:
            remaining[b] -= 1
            if remaining[b] == 0:
                queue.append(b)
    starts = [i for i, n in nm.items() if n.get("data", {}).get("type") == "start"]
    if len(starts) != 1:
        errors.append("expected_one_start_node")
    nested = any(n.get("parentId") or n.get("data", {}).get("type") in {"loop", "iteration"} for n in nodes)
    longest, longest_ids, unreachable = None, [], []
    if len(order) != len(nm):
        errors.append("graph_contains_explicit_cycle")
    elif len(starts) == 1:
        distance = {i: -1 for i in nm}
        prev = {}
        distance[starts[0]] = 1
        for a in order:
            if distance[a] < 0:
                continue
            for b in adjacency[a]:
                if distance[a] + 1 > distance[b]:
                    distance[b], prev[b] = distance[a] + 1, a
        unreachable = [i for i, n in distance.items() if n < 0 and not nm[i].get("parentId")]
        if unreachable:
            warnings.append("unreachable_top_level_nodes:" + ",".join(unreachable))
        end = max(distance, key=distance.get)
        longest = distance[end]
        longest_ids = [end]
        while longest_ids[-1] in prev:
            longest_ids.append(prev[longest_ids[-1]])
        longest_ids.reverse()
    if nested:
        warnings.append("nested_graph_requires_platform_specific_path_and_scope_validation")
        longest = None  # Do not pretend flattened counting proves nested-platform limits.
    if max_path_nodes is not None and longest is not None and longest > max_path_nodes:
        errors.append(f"path_limit_exceeded:{longest}>{max_path_nodes}")
    if max_path_nodes is None:
        warnings.append("platform_path_limit_not_supplied")
    return {**summary(w), "errors": sorted(set(errors)), "warnings": sorted(set(warnings)),
            "nested_graph": nested, "longest_path_nodes": longest, "confirmed_path_limit": max_path_nodes,
            "longest_path": longest_ids if not nested else [], "unreachable_nodes": unreachable,
            "node_inventory": [{"id": i, "title": str(n.get("data", {}).get("title") or "")[:120],
                                "type": n.get("data", {}).get("type"), "reference_count": len(list(references(n.get("data", {})))),
                                "outgoing": [{"condition": e.get("sourceHandle", "source"), "target": e.get("target")}
                                             for e in edges if str(e.get("source")) == i]}
                               for i, n in nm.items()]}


def require_safe_structure(w: dict, max_path_nodes: int | None, *, publishing: bool = False) -> dict:
    r = audit(w, max_path_nodes)
    if r["errors"]:
        raise ValueError("Structural validation failed: " + "; ".join(r["errors"][:8]))
    if r["nested_graph"]:
        raise ValueError("This write adapter does not verify nested workflow semantics; use a reviewed platform-specific adapter")
    if publishing and r["unreachable_nodes"]:
        raise ValueError("Unreachable nodes must be reviewed before publishing")
    return r


def paths_changed(a: Any, b: Any, prefix: str = "") -> list[str]:
    if a == b:
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        found = []
        for k in sorted(set(a) | set(b)):
            path = f"{prefix}.{k}" if prefix else str(k)
            if k not in a or k not in b:
                found.append(path)
            else:
                found.extend(paths_changed(a[k], b[k], path))
        return found
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in paths_changed(x, y, f"{prefix}[{i}]")]
    return [prefix]


def compare(before: dict, after: dict) -> dict:
    before, after = unwrap(before), unwrap(after)
    bc, ac = configuration(before), configuration(after)
    b, a = node_map(bc), node_map(ac)
    changed = [{"id": i, "title": str(a[i].get("data", {}).get("title") or "")[:120],
                "changed_paths": paths_changed(clean(b[i]), clean(a[i]))}
               for i in sorted(set(b) & set(a)) if clean(b[i]) != clean(a[i])]
    b_other = {k: v for k, v in bc.items() if k != "graph"}
    a_other = {k: v for k, v in ac.items() if k != "graph"}
    return {"before": summary(before), "after": summary(after), "added_nodes": sorted(set(a) - set(b)),
            "removed_nodes": sorted(set(b) - set(a)), "changed_nodes": changed,
            "edges_changed": bc["graph"]["edges"] != ac["graph"]["edges"],
            "other_graph_changed_paths": paths_changed(
                {k: v for k, v in bc["graph"].items() if k not in {"nodes", "edges"}},
                {k: v for k, v in ac["graph"].items() if k not in {"nodes", "edges"}}),
            "other_configuration_changed_paths": paths_changed(b_other, a_other)}


def write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("file")
    inspect.add_argument("--max-path-nodes", type=int)
    diff = sub.add_parser("compare")
    diff.add_argument("before")
    diff.add_argument("after")
    p.add_argument("--out", help="New JSON report file; never overwrite an existing file")
    args = p.parse_args()
    result = audit(load_workflow(args.file), args.max_path_nodes) if args.command == "inspect" else compare(load_workflow(args.before), load_workflow(args.after))
    if args.out:
        write_new_json(Path(args.out), result)
        print(json.dumps({"report": str(Path(args.out).resolve()), "errors": result.get("errors", [])}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("errors"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
