"""Exercise access controls and resource boundaries before model execution."""
from __future__ import annotations
import asyncio
from contextlib import contextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.responses import JSONResponse

from backend.config import Settings
from backend.main import create_app
from backend.security import RequestGuardMiddleware, WindowLimiter
from netguard_workflow import ArtifactError

TEST_KEY = "test-only-key-" + "x" * 32

def configuration(**overrides):
    return Settings(_env_file=None, **{"allowed_hosts":["localhost"], "api_key":None, **overrides})

@contextmanager
def client_for(**overrides):
    app = create_app(enable_logging=False, service_settings=configuration(**overrides))
    @app.get("/api/probe")
    def probe():
        return {"ok":True}
    @app.post("/api/probe")
    async def echo(request: Request):
        return await request.json()
    @app.get("/api/broken")
    def broken():
        raise RuntimeError("sensitive internal detail")
    fake = SimpleNamespace(metadata={"name":"test_model"}, artifact_sha256="a"*64)
    with patch("backend.main.get_prediction_service", return_value=fake), TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as client:
        yield client

class SecurityChecks(unittest.TestCase):
    def test_api_key_protects_data_and_health_remains_available(self):
        with client_for(api_key=TEST_KEY) as client:
            self.assertEqual(client.get("/api/probe").status_code, 401)
            self.assertEqual(client.get("/api/probe", headers={"X-API-Key":"wrong"}).status_code, 401)
            self.assertEqual(client.get("/api/probe", headers=[("X-API-Key",TEST_KEY),("X-API-Key",TEST_KEY)]).status_code, 401)
            self.assertEqual(client.get("/api/probe", headers={"X-API-Key":TEST_KEY}).status_code, 200)
            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertNotIn("artifact_sha256", health.json())
            self.assertNotIn("model", health.json())

    def test_shared_mode_requires_key_and_disables_public_docs(self):
        with self.assertRaises(ValidationError):
            configuration(deployment_mode="shared")
        with self.assertRaises(ValidationError):
            configuration(api_key="short")
        with client_for(deployment_mode="shared", api_key=TEST_KEY) as client:
            for path in ["/docs", "/redoc", "/openapi.json"]:
                self.assertEqual(client.get(path, headers={"X-API-Key":TEST_KEY}).status_code, 404)
        self.assertNotIn(TEST_KEY, repr(configuration(api_key=TEST_KEY)))

    def test_untrusted_hosts_and_browser_origins_are_rejected(self):
        with client_for() as client:
            self.assertEqual(client.get("/api/probe", headers={"Host":"attacker.example"}).status_code, 400)
            self.assertEqual(client.get("/api/probe", headers={"Origin":"https://attacker.example"}).status_code, 403)
            self.assertEqual(client.get("/api/probe", headers={"Origin":"null"}).status_code, 403)
            self.assertEqual(client.get("/api/probe", headers={"Origin":"http://localhost:8501"}).status_code, 200)
            self.assertEqual(client.post("/api/probe", json={"ok":1}, headers={"Origin":"http://localhost"}).status_code, 200)
            allowed = client.options("/api/probe", headers={"Origin":"http://localhost:8501", "Access-Control-Request-Method":"POST", "Access-Control-Request-Headers":"X-API-Key,Content-Type"})
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.headers["access-control-allow-origin"], "http://localhost:8501")
            self.assertEqual(client.options("/api/probe", headers={"Host":"attacker.example", "Origin":"http://localhost:8501", "Access-Control-Request-Method":"POST"}).status_code, 400)
            denied = client.options("/api/probe", headers={"Origin":"https://attacker.example", "Access-Control-Request-Method":"POST"})
            self.assertEqual(denied.status_code, 400)
            self.assertNotIn("access-control-allow-origin", denied.headers)
        for values in [{"allowed_hosts":["*"]}, {"cors_origins":["*"]}, {"cors_origins":["https://allowed.example/path"]}]:
            with self.assertRaises(ValidationError):
                configuration(**values)

    def test_body_limit_and_json_content_type(self):
        with client_for(max_request_bytes=1024) as client:
            self.assertEqual(client.post("/api/probe", content=b"x"*1025, headers={"Content-Type":"application/json"}).status_code, 413)
            self.assertEqual(client.post("/api/probe", content="small", headers={"Content-Type":"text/plain"}).status_code, 415)
            self.assertEqual(client.post("/api/probe", json={"ok":1}, headers={"Content-Encoding":"gzip"}).status_code, 415)
            self.assertEqual(client.post("/api/probe", json={"ok":1}, headers={"Content-Type":"application/json; charset=utf-8"}).status_code, 200)
            self.assertEqual(client.post("/api/probe", content=b"{}", headers={"Content-Type":"application/json", "Content-Length":"-1"}).status_code, 400)
            self.assertEqual(client.post("/api/probe", content=b"{}", headers={"Content-Type":"application/json", "Content-Length":"9"*5000}).status_code, 413)

    def test_rate_limit_ignores_spoofed_forwarding_headers(self):
        with client_for(requests_per_minute=2) as client:
            for ip in ["1.2.3.4", "5.6.7.8"]:
                self.assertEqual(client.get("/api/probe", headers={"X-Forwarded-For":ip}).status_code, 200)
            limited = client.get("/api/probe", headers={"X-Forwarded-For":"9.10.11.12"})
            self.assertEqual(limited.status_code, 429)
            self.assertGreater(int(limited.headers["retry-after"]), 0)
            self.assertEqual(client.get("/health").status_code, 200)

    def test_rate_windows_expire_and_memory_is_bounded(self):
        now = [0.]
        limiter = WindowLimiter(1, max_clients=2, clock=lambda:now[0])
        self.assertEqual(limiter.retry_after("one"), 0)
        self.assertEqual(limiter.retry_after("one"), 60)
        self.assertEqual(limiter.retry_after("two"), 0)
        self.assertEqual(limiter.retry_after("three"), 60)
        self.assertEqual(len(limiter.windows), 2)
        now[0] = 60.
        self.assertEqual(limiter.retry_after("three"), 0)
        self.assertEqual(len(limiter.windows), 1)

    def test_errors_have_security_headers_without_internal_details(self):
        with client_for() as client, patch("backend.main.logging.getLogger") as logger:
            for response in [client.get("/api/probe"), client.get("/api/probe", headers={"Host":"bad.example"}), client.get("/api/broken?api_key=do-not-log")]:
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertEqual(response.headers["x-frame-options"], "DENY")
                self.assertNotIn("sensitive internal detail", response.text)
            logger.return_value.exception.assert_called_once_with("Unhandled error on %s", "/api/broken")

    def test_unavailable_model_details_stay_in_server_logs(self):
        with client_for() as client, patch("backend.routes.prediction.get_prediction_service", side_effect=ArtifactError("private/path/model.joblib failed")), patch("backend.main.logging.getLogger") as logger:
            response = client.get("/api/predict/best_model?token=do-not-log")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private/path", response.text)
            self.assertNotIn("model.joblib", response.text)
            self.assertEqual(response.headers["cache-control"], "no-store")
            logger.return_value.error.assert_called_once_with("Service error (%s) on %s: %s", 503, "/api/predict/best_model", "private/path/model.joblib failed")

def scope(headers=()):
    return {"type":"http", "asgi":{"version":"3.0"}, "http_version":"1.1", "scheme":"http", "method":"POST",
            "path":"/api/probe", "raw_path":b"/api/probe", "query_string":b"", "server":("localhost",80), "client":("127.0.0.1",1),
            "headers":[(b"host",b"localhost"),(b"content-type",b"application/json"), *headers]}

async def exchange(guard, chunks, headers=(), delay=0):
    messages = []
    index = 0
    async def receive():
        nonlocal index
        if delay:
            await asyncio.sleep(delay)
        if index >= len(chunks):
            return {"type":"http.disconnect"}
        body = chunks[index]
        index += 1
        return {"type":"http.request", "body":body, "more_body":index < len(chunks)}
    async def send(message):
        messages.append(message)
    await guard(scope(headers), receive, send)
    return next((m["status"] for m in messages if m["type"] == "http.response.start"), None)

class StreamingChecks(unittest.IsolatedAsyncioTestCase):
    async def test_undeclared_and_falsely_small_streams_are_limited_before_parsing(self):
        called = []
        async def downstream(s, receive, send):
            called.append(True)
            await JSONResponse({"ok":True})(s, receive, send)
        guard = RequestGuardMiddleware(downstream, configuration(max_request_bytes=1024))
        for headers in [(), ((b"content-length",b"1"),)]:
            self.assertEqual(await exchange(guard, [b"x"*800,b"y"*225], headers), 413)
        self.assertFalse(called)
        self.assertEqual(guard.active_requests, 0)
        self.assertEqual(await exchange(guard, [b"{}"]), 200)

    async def test_slow_and_disconnected_bodies_release_the_request_slot(self):
        async def downstream(s, receive, send):
            await JSONResponse({"ok":True})(s, receive, send)
        guard = RequestGuardMiddleware(downstream, configuration(request_body_timeout=.01))
        self.assertEqual(await exchange(guard, [b"{}"], delay=.05), 408)
        self.assertIsNone(await exchange(guard, []))
        self.assertEqual(guard.active_requests, 0)
        self.assertEqual(await exchange(guard, [b"{}"]), 200)

    async def test_concurrent_analysis_is_bounded_and_recovers(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def downstream(s, receive, send):
            entered.set()
            await release.wait()
            await JSONResponse({"ok":True})(s, receive, send)
        guard = RequestGuardMiddleware(downstream, configuration(max_inflight_requests=1))
        first = asyncio.create_task(exchange(guard, [b"{}"]))
        await entered.wait()
        self.assertEqual(await exchange(guard, [b"{}"]), 429)
        release.set()
        self.assertEqual(await first, 200)
        self.assertEqual(guard.active_requests, 0)
        self.assertEqual(await exchange(guard, [b"{}"]), 200)

if __name__ == "__main__":
    unittest.main()
