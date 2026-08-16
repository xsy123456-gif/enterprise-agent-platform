"""Request-ID middleware (Phase 18.12)."""

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestIdMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", "")
        if not request_id or not _ID_PATTERN.match(request_id):
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


__all__ = ["RequestIdMiddleware"]
