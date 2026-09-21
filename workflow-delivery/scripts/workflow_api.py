"""Scoped Console adapter. No UI automation; mutations require explicit execution."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from workflow_core import (META, WRITABLE, compare, fingerprint, load_workflow, node_map,
                           read_document, require_safe_structure, summary, unwrap, write_new_json)

MAX_BYTES = 32 * 1024 * 1024
SAFE_PROBE_TYPES = {"llm", "question-classifier", "parameter-extractor", "param-parse",
                    "variable-aggregator", "variable-assigner", "variable-transformation"}


class ApiError(RuntimeError):
    def __init__(self, status: int | None, message: str):
        self.status = status
        super().__init__(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ApiError(code, "Credentialed redirect refused; verify the API root explicitly")


def app_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Application/conversation/run ID must be an explicit UUID") from exc


def safe_node_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Unsupported node ID characters")
    return value


def api_root(value: str, allow_http: bool = False) -> str:
    u = urllib.parse.urlsplit(value)
    if u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError("Provide an explicit http(s) API root without embedded credentials/query/fragment")
    if u.scheme == "http" and not allow_http:
        raise ValueError("HTTP exposes credentials in transit; use HTTPS or explicitly acknowledge --allow-insecure-http")
    return value.rstrip("/")


def target_from_url(value: str) -> dict:
    u = urllib.parse.urlsplit(value.strip())
    if u.scheme not in {"http", "https"} or not u.netloc or u.username or u.password:
        raise ValueError("Unsupported workflow URL")
    # No authentication is extracted or printed, even if a pasted link has query parameters.
    app_match = re.fullmatch(r"(.*)/app/([0-9a-fA-F-]+)/workflow/?", u.path)
    console_match = re.fullmatch(r"(.*?/console/api)/apps/([0-9a-fA-F-]+)/workflows/(draft|publish)/?", u.path)
    if app_match:
        prefix, app = app_match.groups()
        root = prefix + "/console/api"
    elif console_match:
        root, app, _ = console_match.groups()
    else:
        raise ValueError("URL does not match the verified Console adapter; do not guess the API root")
    return {"base_url": urllib.parse.urlunsplit((u.scheme, u.netloc, root, "", "")),
            "app_id": app_uuid(app), "authorization_provided": False,
            "plaintext_http": u.scheme == "http"}


def parse_sse(raw: str) -> list:
    events = []
    for frame in raw.replace("\r\n", "\n").split("\n\n"):
        lines = frame.splitlines()
        data = "\n".join(line[5:].lstrip(" ") for line in lines if line.startswith("data:"))
        if not data or data == "[DONE]":
            continue
        event = next((line[6:].strip() for line in lines if line.startswith("event:")), "message")
        try:
            value = json.loads(data)
        except json.JSONDecodeError:
            value = {"event": event, "unparsed_data": data}
        events.append(value)
    return events


class Client:
    def __init__(self, base: str, app_id: str, token: str, *, allow_http: bool = False, timeout: float = 45):
        self.base = api_root(base, allow_http)
        self.app_id = app_uuid(app_id)
        if not token.strip() or "\r" in token or "\n" in token:
            raise ValueError("Missing or invalid bearer token")
        self._token = token.strip().removeprefix("Bearer ").strip()
        if not self._token or self._token.lower() == "bearer":
            raise ValueError("Missing or invalid bearer token")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, method: str, suffix: str, body=None):
        if not suffix.startswith("/") or suffix.startswith("//") or ".." in urllib.parse.urlsplit(suffix).path.split("/"):
            raise ValueError("Invalid adapter path")
        path = f"/apps/{self.app_id}" + suffix
        encoded = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=encoded, method=method,
            headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream", "User-Agent": "workflow-delivery/1"})
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                chunks, size, started = [], 0, time.monotonic()
                reader = getattr(response, "read1", response.read)
                while True:
                    part = reader(65536)
                    if not part:
                        break
                    chunks.append(part)
                    size += len(part)
                    if size > MAX_BYTES or time.monotonic() - started > 180:
                        raise ApiError(None, "Response limit exceeded; remote execution may still be running")
                raw = b"".join(chunks).decode("utf-8")
                if "text/event-stream" in response.headers.get("Content-Type", "") or raw.lstrip().startswith(("data:", "event:")):
                    return {"events": parse_sse(raw)}
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            # Do not echo a server body that could contain prompts, credentials or PII.
            raise ApiError(exc.code, f"HTTP {exc.code}: {method} {path}; response body withheld") from None
        except (urllib.error.URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise ApiError(None, f"Transport/response error ({type(exc).__name__}); check remote state before retrying writes") from None

    def workflow(self, stage: str) -> dict:
        if stage not in {"draft", "publish"}:
            raise ValueError("Unsupported stage")
        w = unwrap(self.call("GET", f"/workflows/{stage}"))
        if w.get("app_id") and str(w["app_id"]) != self.app_id:
            raise ValueError("API returned a workflow from another application")
        return w


def check_expected(live: dict, expected: dict, app_id: str) -> None:
    if expected.get("app_id") and str(expected["app_id"]) != app_id:
        raise ValueError("Baseline belongs to a different application")
    if fingerprint(live) != fingerprint(expected):
        raise ValueError("Live configuration changed since baseline; refusing overwrite")
    if expected.get("hash") is not None and live.get("hash") != expected.get("hash"):
        raise ValueError("Platform hash changed since baseline; reread instead of overwriting")


def payload_for(candidate: dict, live: dict) -> dict:
    unknown = (set(candidate) | set(live)) - META - WRITABLE
    if unknown:
        raise ValueError("Unverified top-level fields; update the adapter before saving: " + ", ".join(sorted(unknown)))
    missing = (set(live) & WRITABLE) - set(candidate)
    if missing:
        raise ValueError("Candidate omits existing configuration fields: " + ", ".join(sorted(missing)))
    if not live.get("hash"):
        raise ValueError("Current draft has no concurrency hash; adapter requires review")
    payload = {k: copy.deepcopy(v) for k, v in candidate.items() if k in WRITABLE}
    payload["hash"] = live["hash"]
    return payload


def backup(client: Client, out: Path, draft: dict) -> dict | None:
    write_new_json(out / "draft_before.json", draft)
    try:
        published = client.workflow("publish")
    except ApiError as exc:
        if exc.status != 404:
            raise
        published = None
    write_new_json(out / "published_before.json", published)
    write_new_json(out / "target.json", {"base_url": client.base, "app_id": client.app_id,
        "created_at": datetime.now(timezone.utc).isoformat(), "raw_snapshots_may_contain_sensitive_configuration": True})
    return published


def save_draft(client: Client, candidate: dict, expected: dict, out: Path, *, execute: bool, limit: int | None) -> dict:
    if candidate.get("app_id") and str(candidate["app_id"]) != client.app_id:
        raise ValueError("Candidate belongs to a different application; cross-application migration needs an explicit reviewed plan")
    validation = require_safe_structure(candidate, limit)
    live = client.workflow("draft")
    check_expected(live, expected, client.app_id)
    payload_for(candidate, live)  # Detect unsupported schema before even planning a write.
    backup(client, out, live)
    result = {"action": "save-draft", "executed": False, "app_id": client.app_id,
              "diff": compare(live, candidate), "warnings": validation["warnings"]}
    if not execute:
        return result
    # A second read protects the time spent backing up/inspecting.
    fresh = client.workflow("draft")
    check_expected(fresh, live, client.app_id)
    client.call("POST", "/workflows/draft", payload_for(candidate, fresh))
    saved = client.workflow("draft")
    write_new_json(out / "draft_after.json", saved)
    if fingerprint(saved) != fingerprint(candidate):
        raise ValueError("Draft save readback differs; draft may have changed, do not publish or blindly restore")
    result.update(executed=True, verified=summary(saved))
    return result


def publish(client: Client, expected: dict, out: Path, *, execute: bool, limit: int | None) -> dict:
    validation = require_safe_structure(expected, limit, publishing=True)
    live = client.workflow("draft")
    check_expected(live, expected, client.app_id)
    before_pub = backup(client, out, live)
    result = {"action": "publish", "executed": False, "app_id": client.app_id,
              "expected": summary(expected), "warnings": validation["warnings"],
              "published_diff": compare(before_pub, expected) if before_pub else "first_publication",
              "atomic_publish_precondition": "not_provided_by_this_endpoint"}
    if not execute:
        return result
    fresh = client.workflow("draft")
    check_expected(fresh, live, client.app_id)
    client.call("POST", "/workflows/publish", {})
    published = client.workflow("publish")
    write_new_json(out / "published_after.json", published)
    if fingerprint(published) != fingerprint(expected):
        raise ValueError("Published readback differs; publication may have occurred, inspect before further writes")
    result.update(executed=True, verified=summary(published))
    return result


def run_probe(client: Client, expected: dict, node_id: str, inputs: dict, out: Path, *, execute: bool) -> dict:
    node_id = safe_node_id(node_id)
    live = client.workflow("draft")
    check_expected(live, expected, client.app_id)
    n = node_map(live).get(node_id)
    if not n or n.get("data", {}).get("type") not in SAFE_PROBE_TYPES:
        raise ValueError("This probe helper only runs supported non-business-action node types")
    if not isinstance(inputs, dict):
        raise ValueError("Node inputs must be a JSON object")
    result = {"action": "run-node", "executed": False, "node_id": node_id, "node_type": n["data"]["type"]}
    if execute:
        started = time.monotonic()
        raw = client.call("POST", f"/workflows/draft/nodes/{node_id}/run", {"inputs": inputs})
        elapsed = time.monotonic() - started
        write_new_json(out / "node_result.json", raw)
        obj = raw.get("data", raw) if isinstance(raw, dict) else {}
        result.update(executed=True, observed_status=obj.get("status"), evidence="node_result.json",
                      round_trip_seconds=round(elapsed, 3))
    return result


def run_chat(client: Client, expected: dict, body: dict, out: Path, *, execute: bool, allow_effects: bool) -> dict:
    if not isinstance(body, dict) or not isinstance(body.get("query"), str) or not isinstance(body.get("inputs"), dict):
        raise ValueError("Chat body must explicitly provide query:string and inputs:object")
    live = client.workflow("draft")
    check_expected(live, expected, client.app_id)
    result = {"action": "run-chat", "executed": False, "app_id": client.app_id,
              "warning": "Full draft chat can write state, push leads or create groups; use the approved test scope"}
    if execute:
        if not allow_effects:
            raise ValueError("Full workflow execution requires explicit --allow-business-effects after task-level approval")
        started = time.monotonic()
        raw = client.call("POST", "/advanced-chat/workflows/draft/run", body)
        elapsed = time.monotonic() - started
        write_new_json(out / "chat_result.json", raw)
        result.update(executed=True, evidence="chat_result.json", event_count=len(raw.get("events", [])),
                      round_trip_seconds=round(elapsed, 3))
    return result


def get_token(env_name: str | None) -> str:
    if env_name:
        token = os.environ.get(env_name)
        if not token:
            raise ValueError("Requested authentication environment variable is empty")
        return token
    if not sys.stdin.isatty():
        raise ValueError("Use a PTY hidden prompt or an existing process authentication environment variable; no token CLI argument")
    return getpass.getpass("Bearer token (hidden): ")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("target", help="Offline URL extraction; not authentication")
    t.add_argument("url")
    for command in ["snapshot", "messages", "executions", "save-draft", "publish", "run-node", "run-chat"]:
        q = sub.add_parser(command)
        q.add_argument("--base-url", required=True)
        q.add_argument("--app-id", required=True)
        q.add_argument("--out", required=True, help="Controlled project evidence directory; a unique run subdirectory is created")
        q.add_argument("--auth-env", help="Name only; never supply a token as an argument")
        q.add_argument("--allow-insecure-http", action="store_true")
        if command in {"save-draft", "publish", "run-node", "run-chat"}:
            q.add_argument("--expected", required=True, help="Fresh baseline snapshot for concurrency and target checking")
            q.add_argument("--execute", action="store_true", help="Perform the requested action only after current task authorization")
        if command in {"save-draft", "publish"}:
            q.add_argument("--max-path-nodes", type=int, help="Only supply the verified platform limit")
        if command == "save-draft":
            q.add_argument("--candidate", required=True)
        elif command == "messages":
            q.add_argument("--conversation-id", required=True)
            q.add_argument("--limit", type=int, default=100)
        elif command == "executions":
            q.add_argument("--run-id", required=True)
        elif command == "run-node":
            q.add_argument("--node-id", required=True)
            q.add_argument("--inputs", required=True)
        elif command == "run-chat":
            q.add_argument("--body", required=True)
            q.add_argument("--allow-business-effects", action="store_true")
    return p


def main() -> None:
    args = parser().parse_args()
    if args.command == "target":
        print(json.dumps(target_from_url(args.url), ensure_ascii=False, indent=2))
        return
    # Validate identity/transport before asking for secrets.
    base = api_root(args.base_url, args.allow_insecure_http)
    app = app_uuid(args.app_id)
    root = Path(args.out).resolve()
    root.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="workflow-" + args.command + "-", dir=root))
    client = Client(base, app, get_token(args.auth_env), allow_http=args.allow_insecure_http)
    try:
        if args.command == "snapshot":
            draft = client.workflow("draft")
            published = backup(client, out, draft)
            result = {"action": "snapshot", "draft": summary(draft), "published": summary(published) if published else None}
        elif args.command == "messages":
            if not 1 <= args.limit <= 100:
                raise ValueError("Message page limit must be 1..100")
            cid = app_uuid(args.conversation_id)
            query = urllib.parse.urlencode({"conversation_id": cid, "limit": args.limit})
            raw = client.call("GET", "/chat-messages?" + query)
            write_new_json(out / "messages.json", raw)
            result = {"action": "messages", "conversation_id": cid, "scope": "one_page_only", "evidence": "messages.json"}
        elif args.command == "executions":
            rid = app_uuid(args.run_id)
            raw = client.call("GET", f"/workflow-runs/{rid}/node-executions")
            write_new_json(out / "executions.json", raw)
            result = {"action": "executions", "run_id": rid, "evidence": "executions.json"}
        else:
            expected = load_workflow(args.expected)
            if args.command == "save-draft":
                result = save_draft(client, load_workflow(args.candidate), expected, out, execute=args.execute, limit=args.max_path_nodes)
            elif args.command == "publish":
                result = publish(client, expected, out, execute=args.execute, limit=args.max_path_nodes)
            elif args.command == "run-node":
                result = run_probe(client, expected, args.node_id, read_document(args.inputs), out, execute=args.execute)
            else:
                result = run_chat(client, expected, read_document(args.body), out, execute=args.execute, allow_effects=args.allow_business_effects)
        write_new_json(out / "operation_report.json", result)
        print(json.dumps({"evidence_directory": str(out), "action": result["action"],
                          "executed": result.get("executed"), "observed_status": result.get("observed_status")}, ensure_ascii=False))
    except Exception as exc:
        detail = str(exc) if isinstance(exc, (ValueError, ApiError)) else type(exc).__name__
        write_new_json(out / "operation_error.json", {"action": args.command, "error": detail,
            "do_not_blindly_retry": True, "note": "Inspect remote state if any POST may have started; no automatic rollback or retry was performed"})
        print(json.dumps({"error": detail, "evidence_directory": str(out)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
