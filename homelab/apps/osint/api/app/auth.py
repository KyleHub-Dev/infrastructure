"""Remote-User authentication middleware.

Pangolin (IAP) injects a `Remote-User` header on every authenticated request
that passes through the NEWT tunnel. This middleware extracts that identity
and attaches it to the request state.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RemoteUserMiddleware(BaseHTTPMiddleware):
    """Extract the authenticated user identity from the IAP header."""

    def __init__(self, app, header_name: str = "Remote-User"):
        super().__init__(app)
        self.header_name = header_name

    # Paths that don't require authentication
    _PUBLIC_PATHS = {"/api/health", "/api/docs", "/api/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        # Public endpoints bypass auth
        if request.url.path in self._PUBLIC_PATHS:
            return await call_next(request)

        remote_user = request.headers.get(self.header_name)

        if not remote_user:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authentication header. Access this platform through Pangolin."},
            )

        # Attach identity to request state for use in route handlers
        request.state.user = remote_user
        return await call_next(request)
