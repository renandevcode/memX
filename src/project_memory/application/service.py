"""Local application service. Each operation owns one short database transaction."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from project_memory.infrastructure.db import sessions


def new_id() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(UTC).isoformat()


class MemoryError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class MemoryService:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.session_factory = sessions(engine)

    async def project_register(self, *, root: str, name: str) -> dict[str, str]:
        path = Path(root).resolve(strict=True)
        if not path.is_dir():
            raise MemoryError("INVALID_REFERENCE", "Project root must be a directory")
        if not name.strip():
            raise MemoryError("INVALID_INPUT", "Project name is required")
        project_id = new_id()
        async with self.session_factory() as session, session.begin():
            existing = (
                await session.execute(
                    text("SELECT id FROM projects WHERE root=:root"), {"root": str(path)}
                )
            ).scalar_one_or_none()
            if existing:
                raise MemoryError("ALREADY_EXISTS", "Project root is already registered")
            await session.execute(
                text(
                    "INSERT INTO projects (id,name,root,repo_identity,created_at) "
                    "VALUES (:id,:name,:root,:repo_identity,:created_at)"
                ),
                {
                    "id": project_id,
                    "name": name,
                    "root": str(path),
                    "repo_identity": str(path),
                    "created_at": now(),
                },
            )
        return {"schema_version": "1", "id": project_id, "name": name, "root": str(path)}

    async def project_read(self, project_id: str) -> dict[str, str]:
        async with self.session_factory() as session:
            row = (
                (
                    await session.execute(
                        text("SELECT id,name,root,repo_identity FROM projects WHERE id=:id"),
                        {"id": project_id},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise MemoryError("NOT_FOUND", "Project not found")
            return dict(row)
