from pathlib import Path

import pytest

from project_memory.application.service import MemoryError, MemoryService
from project_memory.infrastructure.db import make_engine, migrate


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
