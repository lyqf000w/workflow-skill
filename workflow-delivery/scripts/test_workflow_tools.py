"""Offline contract tests. Uses synthetic workflows and fake transports only."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import workflow_core as core
import workflow_api as api

APP = "11111111-2222-4333-8444-555555555555"
OTHER_APP = "99999999-8888-4777-8666-555555555555"
BASE = "https://workflow.example.invalid/console/api"


def fixture():
    return {
        "app_id": APP, "id": "draft-id", "hash": "hash-1", "version": "draft",
        "graph": {
            "nodes": [
                {"id": "100", "position": {"x": 0, "y": 0},
                 "data": {"type": "start", "title": "入口｜接收消息"}},
                {"id": "200", "position": {"x": 300, "y": 0},
                 "data": {"type": "llm", "title": "咨询｜生成回复", "desc": "读取本轮问题并回复",
                          "prompt_template": [{"role": "system", "text": "{{#sys.query#}}"}],
                          "model": {"name": "example-model"}}},
                {"id": "300", "position": {"x": 600, "y": 0},
                 "data": {"type": "answer", "title": "回复｜发送内容", "desc": "发送上游结果",
                          "answer": "{{#200.text#}}"}},
            ],
            "edges": [
                {"id": "e1", "source": "100", "target": "200", "sourceHandle": "source",
                 "data": {"sourceType": "start", "targetType": "llm"}},
                {"id": "e2", "source": "200", "target": "300", "sourceHandle": "source",
                 "data": {"sourceType": "llm", "targetType": "answer"}},
            ],
        },
        "features": {"opening_statement": "测试开场白"},
        "conversation_variables": [{"name": "customer_name", "value_type": "string", "value": ""}],
        "environment_variables": [],
    }


def changed_fixture():
    w = fixture()
    w["graph"]["nodes"][1]["data"]["prompt_template"][0]["text"] = "新的测试话术 {{#sys.query#}}"
    return w


class FakeClient:
    """Never uses sockets. Records POSTs and simulates concurrency/readback."""
    def __init__(self, draft=None, published=None):
        self.base, self.app_id = BASE, APP
        self.draft = copy.deepcopy(draft if draft is not None else fixture())
        self.published = copy.deepcopy(published if published is not None else fixture())
        self.posts = []
        self.draft_reads = 0
        self.change_on_draft_read = None
        self.bad_save = False
        self.bad_publish = False
        self.publish_read_error = None

    def workflow(self, stage):
        if stage == "draft":
            self.draft_reads += 1
            if self.draft_reads == self.change_on_draft_read:
                self.draft["features"]["opening_statement"] = "concurrent edit"
                self.draft["hash"] = "changed-by-someone-else"
            return copy.deepcopy(self.draft)
        if self.publish_read_error:
            raise self.publish_read_error
        if self.published is None:
            raise api.ApiError(404, "not published")
        return copy.deepcopy(self.published)

    def call(self, method, suffix, body=None):
        if method != "POST":
            raise AssertionError("Unexpected fake transport request")
        self.posts.append((method, suffix, copy.deepcopy(body)))
        if suffix == "/workflows/draft":
            self.draft.update(copy.deepcopy(body))
            self.draft["hash"] = "saved-hash"
            if self.bad_save:
                self.draft["features"]["opening_statement"] = "unexpected server transform"
            return {"result": "success"}
        if suffix == "/workflows/publish":
            self.published = copy.deepcopy(self.draft)
            self.published.update(id="published-id", version="published", hash="published-hash")
            if self.bad_publish:
                self.published["features"]["opening_statement"] = "unexpected publication"
            return {"result": "success"}
        if suffix.startswith("/workflows/draft/nodes/"):
            return {"data": {"status": "failed", "error": "synthetic probe result"}}
        if suffix == "/advanced-chat/workflows/draft/run":
            return {"events": [{"event": "workflow_finished", "data": {"status": "succeeded"}}]}
        raise AssertionError("Unexpected fake POST path")


class CoreTests(unittest.TestCase):
    def test_supported_wrappers(self):
        w = fixture()
        for value in [w, {"workflow": w}, {"data": w}, {"data": {"workflow": w}}]:
            self.assertEqual(core.fingerprint(value), core.fingerprint(w))

    def test_invalid_document(self):
        for value in [[], {"graph": {}}, {"not_workflow": 1}]:
            with self.assertRaises(ValueError):
                core.unwrap(value)

    def test_json_and_optional_yaml_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "workflow.json"
            core.write_new_json(p, {"workflow": fixture()})
            self.assertEqual(core.fingerprint(core.load_workflow(p)), core.fingerprint(fixture()))
            try:
                import yaml
            except ImportError:
                return
            yp = Path(d) / "workflow.yml"
            yp.write_text(yaml.safe_dump({"workflow": fixture()}, allow_unicode=True), encoding="utf-8")
            self.assertEqual(core.fingerprint(core.load_workflow(yp)), core.fingerprint(fixture()))

    def test_valid_flat_graph(self):
        report = core.audit(fixture(), 3)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["longest_path_nodes"], 3)
        self.assertEqual(report["longest_path"], ["100", "200", "300"])

    def test_path_limit(self):
        self.assertIn("path_limit_exceeded:3>2", core.audit(fixture(), 2)["errors"])
        self.assertIn("platform_path_limit_not_supplied", core.audit(fixture())["warnings"])
        with self.assertRaises(ValueError):
            core.audit(fixture(), 0)

    def test_duplicate_node(self):
        w = fixture()
        w["graph"]["nodes"].append(copy.deepcopy(w["graph"]["nodes"][1]))
        self.assertIn("missing_or_duplicate_node_id", core.audit(w)["errors"])

    def test_duplicate_edge(self):
        w = fixture()
        w["graph"]["edges"].append(copy.deepcopy(w["graph"]["edges"][0]))
        self.assertIn("missing_or_duplicate_edge_id", core.audit(w)["errors"])

    def test_dangling_edge(self):
        w = fixture()
        w["graph"]["edges"][1]["target"] = "missing"
        self.assertIn("dangling_edge:e2", core.audit(w)["errors"])

    def test_wrong_edge_type(self):
        w = fixture()
        w["graph"]["edges"][1]["data"]["sourceType"] = "tool"
        self.assertIn("edge_type_mismatch:e2:sourceType", core.audit(w)["errors"])

    def test_broken_reference(self):
        w = fixture()
        w["graph"]["nodes"][2]["data"]["answer"] = "{{#missing.text#}}"
        self.assertIn("missing_reference:300:missing.text", core.audit(w)["errors"])

    def test_conversation_reference_and_duplicates(self):
        w = fixture()
        w["graph"]["nodes"][2]["data"]["answer"] = "{{#conversation.unknown#}}"
        w["conversation_variables"].append(copy.deepcopy(w["conversation_variables"][0]))
        errors = core.audit(w)["errors"]
        self.assertIn("missing_conversation_variable:300:unknown", errors)
        self.assertIn("duplicate_conversation_variable", errors)

    def test_parser_output_reference(self):
        w = fixture()
        w["graph"]["nodes"][1]["data"].update(type="param-parse", outputs=[{"name": "value"}])
        self.assertIn("missing_parser_output:300:200.text", core.audit(w)["errors"])

    def test_explicit_cycle(self):
        w = fixture()
        w["graph"]["edges"].append({"id": "e3", "source": "300", "target": "200"})
        self.assertIn("graph_contains_explicit_cycle", core.audit(w)["errors"])

    def test_unknown_branch_and_else(self):
        w = fixture()
        w["graph"]["nodes"][1]["data"].update(type="if-else", cases=[{"case_id": "yes"}])
        r = core.audit(w)
        self.assertIn("unknown_branch_handle:200:source", r["errors"])
        self.assertIn("unconnected_else_branch:200", r["warnings"])

    def test_unreachable_blocks_publish_only(self):
        w = fixture()
        w["graph"]["nodes"].append({"id": "400", "data": {"type": "answer", "title": "孤立节点"}})
        self.assertEqual(core.audit(w)["unreachable_nodes"], ["400"])
        core.require_safe_structure(w, 10)
        with self.assertRaisesRegex(ValueError, "Unreachable"):
            core.require_safe_structure(w, 10, publishing=True)

    def test_nested_not_flattened_or_auto_written(self):
        w = fixture()
        w["graph"]["nodes"][1]["data"]["type"] = "iteration"
        w["graph"]["edges"][0]["data"]["targetType"] = "iteration"
        w["graph"]["edges"][1]["data"]["sourceType"] = "iteration"
        self.assertIsNone(core.audit(w, 2)["longest_path_nodes"])
        with self.assertRaisesRegex(ValueError, "nested"):
            core.require_safe_structure(w, 2)

    def test_cosmetic_metadata_does_not_change_fingerprint(self):
        a, b = fixture(), fixture()
        b.update(hash="new", id="new", version="published", updated_at=999)
        b["graph"]["nodes"][1]["selected"] = True
        b["graph"]["nodes"][1]["data"]["_runningStatus"] = "running"
        b["graph"]["edges"][0]["selected"] = True
        self.assertEqual(core.fingerprint(a), core.fingerprint(b))
        self.assertFalse(core.compare(a, b)["changed_nodes"])
        self.assertFalse(core.compare(a, b)["edges_changed"])

    def test_business_selected_parameter_is_preserved(self):
        a, b = fixture(), fixture()
        b["graph"]["nodes"][1]["data"]["tool_parameters"] = {"selected": "option-a"}
        self.assertNotEqual(core.fingerprint(a), core.fingerprint(b))
        a = copy.deepcopy(b)
        b["graph"]["nodes"][1]["data"]["tool_parameters"]["selected"] = "option-b"
        self.assertNotEqual(core.fingerprint(a), core.fingerprint(b))

    def test_layout_and_model_are_configuration(self):
        for kind in ["layout", "model", "prompt", "variable"]:
            a, b = fixture(), fixture()
            if kind == "layout":
                b["graph"]["nodes"][1]["position"]["x"] += 1
            elif kind == "model":
                b["graph"]["nodes"][1]["data"]["model"]["name"] = "other-model"
            elif kind == "prompt":
                b = changed_fixture()
            else:
                b["conversation_variables"][0]["value"] = "a name"
            self.assertNotEqual(core.fingerprint(a), core.fingerprint(b), kind)

    def test_diff_accepts_wrappers_without_prompt_content(self):
        a, b = fixture(), changed_fixture()
        report = core.compare({"workflow": a}, {"data": b})
        rendered = json.dumps(report, ensure_ascii=False)
        self.assertIn("prompt_template", rendered)
        self.assertNotIn("新的测试话术", rendered)

    def test_other_graph_configuration_is_visible_in_diff(self):
        a, b = fixture(), fixture()
        b["graph"]["viewport"] = {"x": 0, "y": 0, "zoom": 0.5}
        self.assertEqual(core.compare(a, b)["other_graph_changed_paths"], ["viewport"])

    def test_report_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.json"
            core.write_new_json(p, {"a": 1})
            with self.assertRaises(FileExistsError):
                core.write_new_json(p, {"a": 2})
            self.assertEqual(core.read_document(p), {"a": 1})


class IdentityAndTransportTests(unittest.TestCase):
    def test_target_links_and_query_not_echoed(self):
        for url in [f"https://workflow.example.invalid/app/{APP}/workflow?token=synthetic-secret",
                    f"{BASE}/apps/{APP}/workflows/draft"]:
            result = api.target_from_url(url)
            self.assertEqual(result["base_url"], BASE)
            self.assertEqual(result["app_id"], APP)
            self.assertFalse(result["authorization_provided"])
            self.assertNotIn("synthetic-secret", json.dumps(result))

    def test_target_wrong_shape_refused(self):
        for url in ["https://workflow.example.invalid/home", "file:///tmp/workflow", "https://u:p@workflow.example.invalid"]:
            with self.assertRaises(ValueError):
                api.target_from_url(url)

    def test_http_requires_explicit_acknowledgment(self):
        http = BASE.replace("https:", "http:")
        with self.assertRaises(ValueError):
            api.api_root(http)
        self.assertEqual(api.api_root(http, True), http)

    def test_credentialed_or_query_roots_refused(self):
        for root in [BASE + "?token=x", BASE + "#fragment", "https://user:password@workflow.example.invalid/api"]:
            with self.assertRaises(ValueError):
                api.api_root(root)

    def test_invalid_ids_and_tokens(self):
        for value in ["../other-app", "", "not-a-uuid"]:
            with self.assertRaises(ValueError):
                api.app_uuid(value)
        with self.assertRaises(ValueError):
            api.safe_node_id("../node")
        for token in ["", "Bearer ", "Bearer", "a\nb", "a\rb"]:
            with self.assertRaises(ValueError):
                api.Client(BASE, APP, token)
        self.assertEqual(api.Client(BASE, APP, "Bearer synthetic-token")._token, "synthetic-token")

    def test_redirect_never_forwards_credentials(self):
        req = urllib.request.Request(BASE)
        with self.assertRaises(api.ApiError):
            api.NoRedirect().redirect_request(req, None, 302, "redirect", {}, "https://other.example.invalid")

    def test_actual_request_stays_scoped_using_fake_opener(self):
        captured = []
        class Response(io.BytesIO):
            headers = {"Content-Type": "application/json"}
        class Opener:
            def open(self, req, timeout):
                captured.append(req)
                return Response(b'{"ok": true}')
        c = api.Client(BASE, APP, "synthetic-token")
        c.opener = Opener()
        self.assertTrue(c.call("GET", "/workflows/draft")["ok"])
        self.assertEqual(captured[0].full_url, f"{BASE}/apps/{APP}/workflows/draft")
        self.assertEqual(captured[0].get_header("Authorization"), "Bearer synthetic-token")
        for suffix in ["//another-host", "/../other-app", "https://another-host"]:
            with self.assertRaises(ValueError):
                c.call("GET", suffix)
        self.assertEqual(len(captured), 1)

    def test_http_error_body_is_not_echoed(self):
        c = api.Client(BASE, APP, "synthetic-token")
        class Opener:
            def open(self, req, timeout):
                raise urllib.error.HTTPError(req.full_url, 401, "private message", {}, io.BytesIO(b"private-body"))
        c.opener = Opener()
        with self.assertRaises(api.ApiError) as ctx:
            c.call("GET", "/workflows/draft")
        self.assertEqual(ctx.exception.status, 401)
        self.assertNotIn("private", str(ctx.exception))

    def test_wrong_app_readback_refused(self):
        c = api.Client(BASE, APP, "synthetic-token")
        wrong = fixture()
        wrong["app_id"] = OTHER_APP
        with patch.object(c, "call", return_value=wrong):
            with self.assertRaisesRegex(ValueError, "another application"):
                c.workflow("draft")

    def test_sse_frames_multiline_and_done(self):
        raw = 'event: message\r\ndata: {"event": "answer",\r\ndata: "text": "ok"}\r\n\r\ndata: [DONE]\r\n\r\nevent: error\r\ndata: not-json\r\n\r\n'
        result = api.parse_sse(raw)
        self.assertEqual(result[0], {"event": "answer", "text": "ok"})
        self.assertEqual(result[1], {"event": "error", "unparsed_data": "not-json"})
        self.assertEqual(len(result), 2)


class MutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def test_payload_preserves_optional_configuration(self):
        live = fixture()
        live.update(application_variables=[], reflection_learning={"enabled": False})
        payload = api.payload_for(live, live)
        for field in core.WRITABLE & set(live):
            self.assertEqual(payload[field], live[field])
        self.assertNotIn("app_id", payload)
        self.assertEqual(payload["hash"], live["hash"])

    def test_unknown_live_or_candidate_fields_refused(self):
        for side in ["live", "candidate"]:
            live, candidate = fixture(), fixture()
            (live if side == "live" else candidate)["unknown_business_config"] = {"keep": True}
            with self.assertRaisesRegex(ValueError, "Unverified"):
                api.payload_for(candidate, live)

    def test_omitted_fields_or_missing_hash_refused(self):
        candidate = fixture()
        del candidate["features"]
        with self.assertRaisesRegex(ValueError, "omits"):
            api.payload_for(candidate, fixture())
        live = fixture()
        del live["hash"]
        with self.assertRaisesRegex(ValueError, "hash"):
            api.payload_for(fixture(), live)

    def test_expected_wrong_app_or_stale_hash_refused(self):
        for field, value in [("app_id", OTHER_APP), ("hash", "stale")]:
            expected = fixture()
            expected[field] = value
            with self.assertRaises(ValueError):
                api.check_expected(fixture(), expected, APP)

    def test_save_plan_does_not_post(self):
        c = FakeClient()
        result = api.save_draft(c, changed_fixture(), fixture(), self.out, execute=False, limit=10)
        self.assertFalse(result["executed"])
        self.assertEqual(c.posts, [])
        self.assertTrue((self.out / "draft_before.json").exists())
        self.assertTrue((self.out / "published_before.json").exists())

    def test_save_wrong_candidate_app_refused(self):
        c, candidate = FakeClient(), changed_fixture()
        candidate["app_id"] = OTHER_APP
        with self.assertRaisesRegex(ValueError, "different application"):
            api.save_draft(c, candidate, fixture(), self.out, execute=True, limit=10)
        self.assertEqual(c.posts, [])

    def test_save_stale_baseline_does_not_post(self):
        c = FakeClient(changed_fixture())
        with self.assertRaisesRegex(ValueError, "changed since baseline"):
            api.save_draft(c, changed_fixture(), fixture(), self.out, execute=True, limit=10)
        self.assertEqual(c.posts, [])

    def test_save_concurrent_edit_during_backup_does_not_post(self):
        c = FakeClient()
        c.change_on_draft_read = 2
        with self.assertRaisesRegex(ValueError, "changed since baseline"):
            api.save_draft(c, changed_fixture(), fixture(), self.out, execute=True, limit=10)
        self.assertEqual(c.posts, [])

    def test_save_success_only_saves_and_reads_back(self):
        c = FakeClient()
        result = api.save_draft(c, changed_fixture(), fixture(), self.out, execute=True, limit=10)
        self.assertTrue(result["executed"])
        self.assertEqual([p[1] for p in c.posts], ["/workflows/draft"])
        self.assertEqual(c.posts[0][2]["hash"], "hash-1")
        self.assertEqual(result["verified"]["hash"], "saved-hash")
        self.assertTrue((self.out / "draft_after.json").exists())

    def test_save_mismatch_not_retried_or_published(self):
        c = FakeClient()
        c.bad_save = True
        with self.assertRaisesRegex(ValueError, "readback differs"):
            api.save_draft(c, changed_fixture(), fixture(), self.out, execute=True, limit=10)
        self.assertEqual(len(c.posts), 1)
        self.assertEqual(c.posts[0][1], "/workflows/draft")

    def test_snapshot_non404_failure_blocks_write(self):
        c = FakeClient()
        c.publish_read_error = api.ApiError(403, "forbidden")
        with self.assertRaises(api.ApiError):
            api.save_draft(c, changed_fixture(), fixture(), self.out, execute=True, limit=10)
        self.assertEqual(c.posts, [])

    def test_snapshot_404_records_no_prior_publication(self):
        c = FakeClient()
        c.published = None
        self.assertIsNone(api.backup(c, self.out, fixture()))
        self.assertIsNone(core.read_document(self.out / "published_before.json"))

    def test_publish_plan_no_post(self):
        c = FakeClient()
        result = api.publish(c, fixture(), self.out, execute=False, limit=10)
        self.assertFalse(result["executed"])
        self.assertEqual(c.posts, [])

    def test_publish_stale_or_concurrent_no_post(self):
        for changed_on_read in [1, 2]:
            c = FakeClient()
            c.change_on_draft_read = changed_on_read
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(ValueError, "changed since baseline"):
                    api.publish(c, fixture(), Path(d), execute=True, limit=10)
            self.assertEqual(c.posts, [])

    def test_publish_success_checked_configuration_not_id(self):
        c = FakeClient()
        result = api.publish(c, fixture(), self.out, execute=True, limit=10)
        self.assertTrue(result["executed"])
        self.assertEqual([p[1] for p in c.posts], ["/workflows/publish"])
        self.assertTrue((self.out / "published_after.json").exists())

    def test_publish_mismatch_no_retry(self):
        c = FakeClient()
        c.bad_publish = True
        with self.assertRaisesRegex(ValueError, "Published readback differs"):
            api.publish(c, fixture(), self.out, execute=True, limit=10)
        self.assertEqual(len(c.posts), 1)

    def test_node_probe_plan_no_post(self):
        c = FakeClient()
        result = api.run_probe(c, fixture(), "200", {"#sys.query#": "测试"}, self.out, execute=False)
        self.assertFalse(result["executed"])
        self.assertEqual(c.posts, [])

    def test_node_probe_denies_business_tools(self):
        w = fixture()
        w["graph"]["nodes"][1]["data"]["type"] = "tool"
        c = FakeClient(w)
        with self.assertRaisesRegex(ValueError, "non-business-action"):
            api.run_probe(c, w, "200", {}, self.out, execute=True)
        self.assertEqual(c.posts, [])

    def test_node_result_does_not_conflate_execution_and_success(self):
        c = FakeClient()
        r = api.run_probe(c, fixture(), "200", {}, self.out, execute=True)
        self.assertTrue(r["executed"])
        self.assertEqual(r["observed_status"], "failed")
        self.assertGreaterEqual(r["round_trip_seconds"], 0)
        self.assertEqual(len(c.posts), 1)

    def test_chat_plan_and_missing_effect_ack_no_post(self):
        c = FakeClient()
        body = {"query": "测试问题", "inputs": {}}
        result = api.run_chat(c, fixture(), body, self.out, execute=False, allow_effects=False)
        self.assertFalse(result["executed"])
        with self.assertRaisesRegex(ValueError, "allow-business-effects"):
            api.run_chat(c, fixture(), body, self.out, execute=True, allow_effects=False)
        self.assertEqual(c.posts, [])

    def test_chat_bad_body_no_post(self):
        c = FakeClient()
        for body in [{}, {"query": 1, "inputs": {}}, {"query": "x", "inputs": []}]:
            with self.assertRaises(ValueError):
                api.run_chat(c, fixture(), body, self.out, execute=True, allow_effects=True)
        self.assertEqual(c.posts, [])

    def test_chat_executes_once_and_retains_evidence(self):
        c = FakeClient()
        result = api.run_chat(c, fixture(), {"query": "测试问题", "inputs": {}}, self.out, execute=True, allow_effects=True)
        self.assertTrue(result["executed"])
        self.assertEqual(len(c.posts), 1)
        self.assertEqual(result["event_count"], 1)
        self.assertGreaterEqual(result["round_trip_seconds"], 0)
        self.assertTrue((self.out / "chat_result.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
