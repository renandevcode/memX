"""Local command-line interface using the application service."""

import asyncio
import json
from typing import Any

import typer

from project_memory.application.service import MemoryError, MemoryService
from project_memory.config import Settings
from project_memory.infrastructure.db import make_engine, migrate

app = typer.Typer(help="MemX local memory operations")


@app.command("init")
def init_database() -> None:
    """Apply versioned migrations to the configured local database."""
    migrate(Settings().db_url)
    typer.echo("Database migrated")


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
        engine = make_engine(Settings().db_url)
        try:
            method = getattr(MemoryService(engine), operation)
            result: dict[str, Any] = await method(**payload)
            return result
        finally:
            await engine.dispose()

    try:
        typer.echo(json.dumps(asyncio.run(run()), ensure_ascii=False))
    except MemoryError as exc:
        typer.echo(json.dumps({"error": exc.code, "detail": exc.detail}), err=True)
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()
