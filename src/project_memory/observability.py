"""Bounded JSON diagnostics for public operations; never logs request bodies."""

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

from project_memory.application.service import MemoryError

logger = logging.getLogger("memx.operations")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


@contextmanager
def operation_span(operation: str, project_id: str | None = None) -> Iterator[str]:
    request_id = uuid4().hex
    started = time.monotonic()
    code = "OK"
    try:
        yield request_id
    except MemoryError as exc:
        code = exc.code
        raise
    except Exception:
        code = "INTERNAL_ERROR"
        raise
    finally:
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "project_id": project_id,
                    "operation": operation,
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                    "schema_version": 1,
                    "code": code,
                },
                separators=(",", ":"),
            )
        )
