import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from project_memory.application.service import MemoryError, MemoryService
from project_memory.infrastructure.db import make_engine, migrate


def test_upgrade_existing_database_preserves_project(tmp_path: Path) -> None:
    db_path = tmp_path / "existing.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "0001")

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO projects (id, name, root, repo_identity, created_at) VALUES (?, ?, ?, ?, ?)",
            ("existing-project", "Existing", str(tmp_path), "existing", "2026-01-01T00:00:00Z"),
        )

    migrate(db_url)
    migrate(db_url)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0002",)
        assert connection.execute("SELECT name FROM projects WHERE id = ?", ("existing-project",)).fetchone() == (
            "Existing",
        )
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'memory_fts'").fetchone() == (
            "memory_fts",
        )


@pytest.mark.asyncio
async def test_migration_and_explicit_project_identity(tmp_path: Path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'state.sqlite3'}"
    migrate(db_url)
    engine = make_engine(db_url)
    service = MemoryService(engine)
    project = await service.project_register(root=str(tmp_path), name="OCR")
    assert (await service.project_read(project["id"]))["root"] == str(tmp_path)
    with pytest.raises(MemoryError, match="Project root is already registered"):
        await service.project_register(root=str(tmp_path), name="Duplicate")
    await engine.dispose()

    reopened = make_engine(db_url)
    assert (await MemoryService(reopened).project_read(project["id"]))["name"] == "OCR"
    await reopened.dispose()
