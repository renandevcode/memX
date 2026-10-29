"""Local command-line interface using the application service."""

import asyncio
import ipaddress
import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError

from project_memory.application.handoff import MemoryService
from project_memory.application.service import MemoryError
from project_memory.config import Settings
from project_memory.infrastructure.db import make_engine, migrate
from project_memory.interfaces.binding import resolve_binding
from project_memory.interfaces.contracts import validate_arguments

app = typer.Typer(help="MemX local memory operations")


@app.command("db-init")
def init_database() -> None:
    """Apply versioned migrations to the configured local database."""
    migrate(Settings().db_url)
    typer.echo("Database migrated")


@app.command("init")
def init_project(root: Annotated[Path, typer.Option("--root")] = Path(".")) -> None:
    """Enable MemX for this project, preserving existing agent instructions."""
    from project_memory.interfaces.activation import activate

    settings = Settings()
    migrate(settings.db_url)
    try:
        result = asyncio.run(activate(root, settings))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result))


@app.command("serve-http")
def serve_http() -> None:
    """Serve the token-protected local API on a loopback address."""
    import uvicorn

    from project_memory.interfaces.http import create_app

    config = Settings()
    if not ipaddress.ip_address(config.http_host).is_loopback:
        raise typer.BadParameter("HTTP host must be a loopback address")
    migrate(config.db_url)
    uvicorn.run(create_app(config), host=config.http_host, port=config.http_port)


@app.command("call")
def call(operation: str, arguments: str = typer.Argument("{}")) -> None:
    """Call a service operation with JSON keyword arguments."""
    allowed = {
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
    if operation not in allowed:
        raise typer.BadParameter("Unknown operation")
    try:
        payload = json.loads(arguments)
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
    except (json.JSONDecodeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    async def run() -> dict[str, Any]:
        settings, binding = resolve_binding()
        if binding and operation != "project_register":
            if payload.get("project_id", binding.project_id) != binding.project_id:
                raise MemoryError("ACCESS_DENIED", "Project differs from current activation")
            payload["project_id"] = binding.project_id
        engine = make_engine(settings.db_url)
        try:
            service = MemoryService(engine)
            if binding:
                project = await service.project_read(binding.project_id)
                if project["root"] != binding.root:
                    raise MemoryError("ACCESS_DENIED", "Database project root differs from activation")
            method = getattr(service, operation)
            result: dict[str, Any] = await method(**validate_arguments(operation, payload))
            return result
        finally:
            await engine.dispose()

    try:
        typer.echo(json.dumps(asyncio.run(run()), ensure_ascii=False))
    except ValidationError as exc:
        typer.echo("INVALID_INPUT: arguments do not match the operation schema", err=True)
        raise typer.Exit(1) from exc
    except MemoryError as exc:
        typer.echo(json.dumps({"error": exc.code, "detail": exc.detail}), err=True)
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()
