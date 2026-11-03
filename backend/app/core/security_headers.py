"""Response headers that tell browsers to be strict with what the API sends."""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Everything this API returns is JSON, so nothing needs to load or be framed.
_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # Responses hold one person's private data; shared caches must not keep them.
    "Cache-Control": "no-store",
}
_HSTS = "max-age=63072000; includeSubDomains"


class SecurityHeadersMiddleware:
    """Plain ASGI middleware, so streamed responses are not buffered."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # The interactive docs (development only) load their own scripts and styles.
        is_docs = scope["path"].startswith("/api/docs")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _HEADERS.items():
                    if is_docs and name == "Content-Security-Policy":
                        continue
                    headers.setdefault(name, value)
                if self.hsts:
                    headers.setdefault("Strict-Transport-Security", _HSTS)
            await send(message)

        await self.app(scope, receive, send_with_headers)
