"""
Middleware tracer: menambahkan Request ID, timing, dan request logging.

Setiap request yang masuk akan mendapatkan:
- X-Request-ID (di response header) untuk tracing
- Timing (duration_ms) di log
- Request body logging (tanpa sensitive data)

 penggunaan di main.py:
   from apps.middleware.tracer import TracerMiddleware
   app.add_middleware(TracerMiddleware)
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from apps.bootstrap.logger import log_error, log_request


class TracerMiddleware(BaseHTTPMiddleware):
    """
    Middleware untuk:
    - Membuat request ID unik per request
    - Mengukur durasi request
    - Meloginkan request (method, path, status, duration, body)
    """

    REQUEST_ID_HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate atau ambil request ID
        request_id = request.headers.get(self.REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Store request_id di request state agar handler bisa akses
        request.state.request_id = request_id

        # Capture request body (untuk logging) — hanya untuk POST/PUT/PATCH
        # Di Starlette BaseHTTPMiddleware, setelah await request.body() dipanggil,
        # body otomatis dicache sehingga handler downstream tetap bisa membaca.
        body: Optional[bytes] = None
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()

        start_time = time.perf_counter()

        # Process request
        try:
            response: Response = await call_next(request)
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_error(
                error_type=type(e).__name__,
                message=str(e),
                path=request.url.path,
                request_id=request_id,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Parse request body untuk log (jika ada)
        request_body = None
        if body:
            try:
                request_body = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_body = body.decode("utf-8", errors="replace")

        # Log request
        try:
            log_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                request_body=request_body,
                request_id=request_id,
                duration_ms=round(duration_ms, 2),
            )
        except Exception:
            pass  # Logging tidak boleh mengganggu response

        # Tambahkan request ID ke response header
        response.headers[self.REQUEST_ID_HEADER] = request_id

        return response
