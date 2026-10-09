import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from org_audit.api import AuditAPIError, GitHubAPI
from org_audit.collector import collect, validate_org
from org_audit.review import recommend
from org_audit.dashboard import render
from org_audit.cli import main

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


class Response:
    def __init__(self, payload, headers=None):
        self.payload = json.dumps(payload).encode()
        self.headers = headers or {}
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return self.payload


class API(unittest.TestCase):
    def test_get_is_read_only_and_token_not_in_url(self):
        seen = []
        def open_(request, timeout):
            seen.append((request.get_method(), request.full_url, request.get_header("Authorization"), timeout))
            return Response([])
        api = GitHubAPI("secret-example", opener=open_, retries=0)
        self.assertEqual(api.get("/orgs/demo/repos")[0], [])
        self.assertEqual(seen[0][0], "GET")
        self.assertNotIn("secret-example", seen[0][1])
        self.assertEqual(seen[0][2], "Bearer secret-example")
        with self.assertRaises(ValueError): api.get("https://attacker.invalid/steal")

    def test_pagination_and_cap(self):
        calls = []
        def open_(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                return Response([1], {"Link": '<https://api.github.com/page2>; rel="next"'})
            return Response([2])
        api = GitHubAPI("token", opener=open_, retries=0)
        self.assertEqual(api.pages("/page1"), ([1, 2], False))
        calls.clear()
        self.assertEqual(api.pages("/page1", max_pages=1), ([1], True))

    def test_server_error_retries_only_within_limit(self):
        attempts = []
        def flaky(request, timeout):
            attempts.append(request.get_method())
            if len(attempts) == 1:
                raise HTTPError(request.full_url, 503, "unavailable", {}, io.BytesIO(b""))
            return Response([{"ok": True}])
        api = GitHubAPI("test-token", opener=flaky, retries=1, sleep=lambda _: None)
        self.assertEqual(api.get("/orgs/demo/repos")[0], [{"ok": True}])
        self.assertEqual(attempts, ["GET", "GET"])

    def test_auth_error_and_bounded_retry(self):
        calls = []
        def denied(request, timeout):
            calls.append(request.get_method())
            raise HTTPError(request.full_url, 403, "denied", {}, io.BytesIO(b'{"message":"secret-example"}'))
        api = GitHubAPI("secret-example", opener=denied, retries=2, sleep=lambda _: None)
        with self.assertRaisesRegex(AuditAPIError, "insufficient read permissions") as caught:
            api.get("/orgs/demo/repos")
        self.assertNotIn("secret-example", str(caught.exception))
        self.assertEqual(calls, ["GET"])


class Review(unittest.TestCase):
    def setUp(self):
        self.repo = {"name":"api","created_at":"2025-01-01T00:00:00Z","archived":False}
        self.grants = [{"login":"alex","permission":"admin","outside":True}]
    def test_owner_bot_new_and_archived_excluded(self):
        self.assertEqual(recommend(self.repo,self.grants,{}, {"alex"},now=NOW), [])
        self.assertEqual(recommend(self.repo,[{"login":"ci[bot]","permission":"admin"}],{},set(),now=NOW), [])
        self.assertEqual(recommend({**self.repo,"archived":True},self.grants,{},set(),now=NOW), [])
        self.assertEqual(recommend({**self.repo,"created_at":"2026-10-01T00:00:00Z"},self.grants,{},set(),now=NOW), [])
    def test_evidence_and_uncertainty(self):
        self.assertEqual(recommend(self.repo,self.grants,{"alex":{"commits":1}},set(),now=NOW), [])
        result = recommend(self.repo,self.grants,{},set(),now=NOW,evidence_complete=False)
        self.assertEqual(result[0]["severity"], "high")
        self.assertIn("incomplete", result[0]["uncertainty"])
        self.assertIn("Confirm", result[0]["action"])


class Collector(unittest.TestCase):
    def test_invalid_org(self):
        with self.assertRaises(ValueError): validate_org("../other")
    def test_partial_data_suppresses_recommendation(self):
        class Fake:
            def pages(self,path,*,max_pages):
                if "outside_collaborators" in path:
                    raise AuditAPIError("forbidden")
                if path.endswith("repos?type=all&per_page=100"):
                    return ([{"name":"api","created_at":"2025-01-01T00:00:00Z","html_url":"https://github.com/demo/api"}],False)
                if "collaborators?" in path:
                    return ([{"login":"alex","role_name":"admin"}],False)
                return ([],False)
        result=collect(Fake(),"demo")
        self.assertEqual(result["recommendations"], [])
        self.assertTrue(result["warnings"])
        self.assertIn("suppressed",result["notes"][0])
    def test_listing_failure_is_fatal(self):
        class Fake:
            def pages(self,*a,**kw): raise AuditAPIError("not accessible")
        with self.assertRaises(AuditAPIError): collect(Fake(),"demo")


class DashboardCLI(unittest.TestCase):
    def test_escaped_output_and_blocked_external_link(self):
        data={"mode":"mock","organization":"<script>alert(1)</script>","repositories":[{"name":"<img src=x>","url":"javascript:alert(1)"}]}
        html=render(data)
        self.assertNotIn("<script>alert(1)</script>",html)
        self.assertIn("&lt;img src=x&gt;",html)
        self.assertNotIn('href="javascript:',html)
    def test_mock_generates_and_live_without_token_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            self.assertEqual(main(["mock","--out",str(out)]),0)
            self.assertIn("northstar-demo",(out/"dashboard.html").read_text())
            self.assertEqual(json.loads((out/"audit.json").read_text())["mode"],"mock")
            with patch.dict(os.environ, {"GITHUB_TOKEN":""}):
                self.assertEqual(main(["live","--org","demo","--out",str(out)]),2)
            self.assertEqual(json.loads((out/"audit.json").read_text())["mode"],"mock")

if __name__ == "__main__": unittest.main()
