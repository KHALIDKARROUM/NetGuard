"""Bounded ASGI request handling and access controls for the research API."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import math
import secrets
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.config import Settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_headers(message: Message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers[name] = value
                if not scope["path"].startswith(("/docs", "/redoc")):
                    headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
            await send(message)

        await self.app(scope, receive, send_headers)


class WindowLimiter:
    """Per-worker fixed windows with bounded memory; use an edge limiter for a fleet."""
    def __init__(self, limit: int, max_clients: int = 4096, clock=time.monotonic):
        self.limit = limit
        self.max_clients = max_clients
        self.clock = clock
        self.windows: OrderedDict[str, tuple[float, int]] = OrderedDict()

    def retry_after(self, client: str) -> int:
        now = self.clock()
        while self.windows and now - next(iter(self.windows.values()))[0] >= 60:
            self.windows.popitem(last=False)
        if client not in self.windows:
            if len(self.windows) >= self.max_clients:
                return 60
            self.windows[client] = (now, 1)
            return 0
        started, count = self.windows[client]
        if count >= self.limit:
            return max(1, math.ceil(60 - (now - started)))
        self.windows[client] = (started, count + 1)
        return 0


class BodyTooLarge(Exception):
    pass


class ClientDisconnected(Exception):
    pass


class RequestGuardMiddleware:
    """Reject unauthorized or oversized requests before JSON parsing and inference."""
    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings
        self.key = settings.api_key.get_secret_value().encode("ascii") if settings.api_key else None
        self.limiter = WindowLimiter(settings.requests_per_minute)
        self.active_requests = 0

    async def _body(self, receive: Receive) -> bytes:
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise ClientDisconnected
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.settings.max_request_bytes:
                raise BodyTooLarge
            chunks.append(chunk)
            if not message.get("more_body", False):
                return b"".join(chunks)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)

        async def reject(status: int, detail: str, extra: dict | None = None):
            await JSONResponse({"detail": detail}, status_code=status, headers=extra)(scope, receive, send)

        origins = headers.getlist("origin")
        same_origin = f"{scope.get('scheme', 'http')}://{headers.get('host', '')}"
        if origins and (len(origins) != 1 or origins[0] not in [*self.settings.cors_origins, same_origin]):
            return await reject(403, "This browser origin is not allowed.")

        if scope["path"] != "/health":
            # Forwarding headers are deliberately not read here. Configure trusted proxies in the server.
            client = (scope.get("client") or ("unknown", 0))[0]
            retry = self.limiter.retry_after(client)
            if retry:
                return await reject(429, "Too many requests. Try again later.", {"Retry-After": str(retry)})
            if self.key is not None:
                keys = headers.getlist("x-api-key")
                supplied = keys[0].encode("latin-1") if len(keys) == 1 else b""
                if not secrets.compare_digest(supplied, self.key):
                    return await reject(401, "A valid API key is required.", {"WWW-Authenticate": 'APIKey realm="NetGuard"'})

        lengths = headers.getlist("content-length")
        if lengths and (len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal()):
            return await reject(400, "Invalid Content-Length header.")
        if lengths:
            normalized_length = lengths[0].lstrip("0") or "0"
            if len(normalized_length) > len(str(self.settings.max_request_bytes)) or int(normalized_length) > self.settings.max_request_bytes:
                return await reject(413, "Request body exceeds the configured size limit.")
        if headers.get("content-encoding", "identity").lower() != "identity":
            return await reject(415, "Compressed request bodies are not supported.")
        if scope["method"] == "POST" and scope["path"].startswith("/api/"):
            if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                return await reject(415, "Prediction requests must use application/json.")

        analyzing = scope["path"].startswith("/api/")
        if analyzing and self.active_requests >= self.settings.max_inflight_requests:
            return await reject(429, "The analysis service is busy. Try again shortly.", {"Retry-After": "1"})
        if analyzing:
            self.active_requests += 1
        try:
            try:
                body = await asyncio.wait_for(self._body(receive), timeout=self.settings.request_body_timeout)
            except BodyTooLarge:
                return await reject(413, "Request body exceeds the configured size limit.")
            except asyncio.TimeoutError:
                return await reject(408, "Request body timed out.")
            except ClientDisconnected:
                return
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await self.app(scope, replay, send)
        finally:
            if analyzing:
                self.active_requests -= 1
