"""Structured logs: one JSON object per line on stdout.

Railway and DO collect stdout. JSON lines can be filtered by field, so "every
line for request abc123" or "every 5xx today" is a query instead of a grep.
"""

import json
import logging
import re
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HANDLER_NAME = "oner-json"

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

log = logging.getLogger("oner.request")

# An incoming X-Request-ID (a proxy may set one) is echoed back as a header and
# written into every log line, so only a short plain token is reused.
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

_REQUEST_FIELDS = ("method", "path", "status", "duration_ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if getattr(record, "request_id", None) is not None:
            entry["request_id"] = record.request_id
        for field in _REQUEST_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def _stamping(factory):
    """Wrap the log record factory so every record carries the current request id.

    Stamped when the record is created, not when it's formatted, so the id is
    still right for handlers that format later, like pytest's log capture.
    """

    def make(*args, **kwargs):
        record = factory(*args, **kwargs)
        record.request_id = request_id.get()
        return record

    make.stamps_request_id = True
    return make


def setup_logging(level: int = logging.INFO) -> None:
    """Route the app's and uvicorn's logs through one JSON handler on stdout.

    Safe to call more than once: only our own handler is replaced, so pytest's
    log capture keeps working.
    """
    if not getattr(logging.getLogRecordFactory(), "stamps_request_id", False):
        logging.setLogRecordFactory(_stamping(logging.getLogRecordFactory()))

    root = logging.getLogger()
    for handler in [h for h in root.handlers if h.get_name() == HANDLER_NAME]:
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn gives its loggers plain-text handlers before the app is imported.
    # Send them through the root handler instead. The access log goes quiet:
    # RequestLogMiddleware writes a richer line for every request.
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True


class RequestLogMiddleware:
    """One log line per request, plus an X-Request-ID that ties together every
    line written while handling it.

    An exception nothing else caught is logged here with its traceback and
    answered as a JSON 500, so a client never sees a plain-text error page.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        sent = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        rid = sent if _SAFE_REQUEST_ID.fullmatch(sent) else uuid4().hex
        token = request_id.set(rid)
        start = time.perf_counter()
        status = 500
        started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", rid)
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            # The one deliberate catch-all. Whatever it was gets logged with a
            # traceback, and the client gets a 500 that leaks nothing.
            log.exception("unhandled error")
            if started:
                raise  # headers already went out; there's no response to replace
            status = 500
            response = JSONResponse(
                {"detail": "Internal server error"},
                status_code=500,
                headers={"X-Request-ID": rid},
            )
            await response(scope, receive, send)
        finally:
            log.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            request_id.reset(token)
