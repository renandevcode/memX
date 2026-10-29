"""Per-operation DTOs shared by local transports; schema version 1."""

import inspect
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, TypeAdapter, create_model

from project_memory.application.handoff import MemoryService

OPERATIONS = {
    "project_register",
    "project_read",
    "task_create",
    "task_read",
    "task_transition",
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


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProjectCreated(Output):
    schema_version: str
    id: str
    name: str
    root: str


class ProjectRead(Output):
    id: str
    name: str
    root: str
    repo_identity: str


class Task(Output):
    id: str
    project_id: str
    title: str
    objective: str
    acceptance_criteria: list[str]
    scope: str
    status: str
    version: int


class TaskTransitioned(Output):
    id: str
    status: str
    version: int


class SessionStarted(Output):
    id: str
    project_id: str
    task_id: str | None
    host: str
    status: str


class SessionEnded(Output):
    id: str
    status: str


class Event(Output):
    id: str
    sequence: int


class Evidence(Output):
    id: str
    verification_status: str


class CheckpointCreated(Output):
    id: str
    task_version: int
    event_watermark: int


class Checkpoint(Output):
    id: str
    project_id: str
    task_id: str
    task_version: int
    session_id: str
    idempotency_key: str
    fingerprint: str
    completed: list[str]
    pending: list[str]
    blockers: list[str]
    next_action: str
    changed_paths: list[str]
    evidence_refs: list[str]
    checkout_ref: dict[str, Any]
    event_watermark: int
    created_at: str


class MemoryChanged(Output):
    id: str
    version: int
    status: str


class MemoryRead(Output):
    id: str
    project_id: str
    category: str
    scope: str
    status: str
    source_kind: str
    source_document_id: str | None
    current_version: int
    visibility: str
    deleted_at: str | None
    record_id: str
    version: int
    title: str
    body: str
    source_refs: list[str]
    valid_for: dict[str, Any]
    created_at: str
    actor_id: str
    reason: str


class MemoryDeleted(Output):
    id: str
    deleted: bool
    scope: list[str]
    excluded: list[str]


class Relation(Output):
    id: str
    relation_type: str


class SourceIndexed(Output):
    source_id: str
    record_id: str
    version: int
    content_hash: str


class SearchHit(Output):
    id: str
    category: str
    scope: str
    status: str
    current_version: int
    title: str
    snippet: str
    source_refs: list[str]


class SearchResults(Output):
    items: list[SearchHit]
    next_cursor: int | None


class Context(Output):
    schema_version: int
    task_state: dict[str, Any]
    policy_refs: list[str]
    selected_items: list[dict[str, Any]]
    source_refs: list[str]
    warnings: list[str]
    missing_required: list[str]
    usage: dict[str, Any]


class HandoffCreated(Output):
    id: str
    state: str
    version: int


class HandoffAccepted(Output):
    id: str
    state: str
    version: int
    task_id: str
    checkpoint: Checkpoint


OUTPUT_TYPES: dict[str, Any] = {
    "project_register": ProjectCreated,
    "project_read": ProjectRead,
    "task_create": Task,
    "task_read": Task,
    "task_transition": TaskTransitioned,
    "session_start": SessionStarted,
    "session_end": SessionEnded,
    "event_append": Event,
    "evidence_create": Evidence,
    "task_checkpoint": CheckpointCreated,
    "checkpoint_read": Checkpoint,
    "memory_create": MemoryChanged,
    "memory_read": MemoryRead,
    "memory_update": MemoryChanged,
    "memory_archive": MemoryChanged,
    "memory_delete": MemoryDeleted,
    "memory_search": SearchResults,
    "memory_reindex": int,
    "relation_create": Relation,
    "source_index": list[SourceIndexed],
    "context_build": Context,
    "handoff_create": HandoffCreated,
    "handoff_accept": HandoffAccepted,
}
OUTPUT_ADAPTERS = {operation: TypeAdapter(output_type) for operation, output_type in OUTPUT_TYPES.items()}


def validate_output(operation: str, value: Any) -> Any:
    return OUTPUT_ADAPTERS[operation].validate_python(value, strict=True)


def validate_arguments(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return CONTRACTS[operation].model_validate(arguments).model_dump()
