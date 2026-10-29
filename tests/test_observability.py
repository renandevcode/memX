import json
import logging

import pytest

from project_memory.application.service import MemoryError
from project_memory.observability import logger, operation_span


def test_operation_logs_identifiers_and_error_without_payload(caplog: pytest.LogCaptureFixture) -> None:
    secret = "sensitive-body-must-not-appear"
    logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger="memx.operations"):
            with pytest.raises(MemoryError):
                with operation_span("memory_read", "project-1"):
                    raise MemoryError("NOT_FOUND", secret)
    finally:
        logger.removeHandler(caplog.handler)
    entry = json.loads(caplog.records[-1].message)
    assert entry["operation"] == "memory_read"
    assert entry["project_id"] == "project-1"
    assert entry["code"] == "NOT_FOUND"
    assert entry["schema_version"] == 1
    assert entry["duration_ms"] >= 0
    assert len(entry["request_id"]) == 32
    assert secret not in caplog.text
