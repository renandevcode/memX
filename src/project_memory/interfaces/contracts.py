"""Per-operation DTOs shared by local transports; schema version 1."""

import inspect
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, create_model

from project_memory.application.handoff import MemoryService

OPERATIONS = {
    "project_register",
    "project_read",
    "task_create",
    "task_read",
    "session_start",
    "session_end",
    "event_append",
    "evidence_create",
    "task_checkpoint",
    "checkpoint_read",
    "memory_create",
    "memory_read",
    "memory_update",
    "memory_archive",
    "memory_delete",
    "memory_search",
    "memory_reindex",
    "relation_create",
    "source_index",
    "context_build",
    "handoff_create",
    "handoff_accept",
}


def operation_model(operation: str, project_id: str | None = None) -> type[BaseModel]:
    method = getattr(MemoryService, operation)
    hints = get_type_hints(method)
    fields: dict[str, Any] = {}
    for name, parameter in inspect.signature(method).parameters.items():
        if name in {"self", "fail_after_update"}:
            continue
        default = ... if parameter.default is inspect.Parameter.empty else parameter.default
        if name == "project_id" and project_id is not None:
            default = project_id
        fields[name] = (hints[name], default)
    return create_model(operation + "Arguments", __config__=ConfigDict(extra="forbid", strict=True), **fields)


CONTRACTS = {operation: operation_model(operation) for operation in OPERATIONS}


def validate_arguments(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return CONTRACTS[operation].model_validate(arguments).model_dump()
