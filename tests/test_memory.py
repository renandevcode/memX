from pathlib import Path

import pytest

from project_memory.application.memory import MemoryService
from project_memory.application.service import MemoryError
from project_memory.infrastructure.db import make_engine, migrate


@pytest.mark.asyncio
async def test_versioned_memory_search_delete_and_source_scope(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    other_root = tmp_path / "other"
    project_root.mkdir()
    other_root.mkdir()
    url = f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"
    migrate(url)
    engine = make_engine(url)
    service = MemoryService(engine)
    project = await service.project_register(root=str(project_root), name="OCR")
    other = await service.project_register(root=str(other_root), name="Other")
    pid = project["id"]
    record = await service.memory_create(
        project_id=pid,
        category="decisions",
        title="Rotation",
        body="Use async processing",
        scope="ocr",
        status="active",
    )
    rid = record["id"]
    assert len((await service.memory_search(project_id=pid, query="async", scope="ocr"))["items"]) == 1
    assert (await service.memory_search(project_id=other["id"], query="async"))["items"] == []
    with pytest.raises(MemoryError) as cross:
        await service.memory_create(
            project_id=other["id"],
            category="findings",
            title="Cross",
            body="Invalid",
            source_refs=[rid],
        )
    assert cross.value.code == "INVALID_REFERENCE"
    changed = await service.memory_update(
        project_id=pid,
        record_id=rid,
        expected_version=1,
        title="Rotation v2",
        body="Use async workers",
        reason="Measured",
        status="active",
    )
    assert changed["version"] == 2
    assert (await service.memory_read(pid, rid, 1))["body"] == "Use async processing"
    with pytest.raises(MemoryError) as stale:
        await service.memory_update(
            project_id=pid,
            record_id=rid,
            expected_version=1,
            title="Stale",
            body="Stale",
            reason="Retry",
        )
    assert stale.value.code == "VERSION_CONFLICT"
    result = await service.memory_delete(project_id=pid, record_id=rid, expected_version=2, reason="Remove test data")
    assert result["deleted"] is True
    assert (await service.memory_search(project_id=pid, query="async"))["items"] == []
    assert await service.memory_reindex(pid) == 0
    assert (await service.memory_search(project_id=pid, query="async", include_history=True))["items"] == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_required_policy_context_budget_and_changed_source(tmp_path: Path) -> None:
    root = tmp_path / "ocr"
    root.mkdir()
    policy_file = root / "POLICY.md"
    policy_file.write_text("Mandatory: use async processing for OCR.")
    url = f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"
    migrate(url)
    engine = make_engine(url)
    service = MemoryService(engine)
    pid = (await service.project_register(root=str(root), name="OCR"))["id"]
    sources = await service.source_index(project_id=pid, paths=["POLICY.md"], scope="ocr")
    task = await service.task_create(
        project_id=pid,
        title="OCR task",
        objective="Fix rotation",
        acceptance_criteria=["fixture passes"],
        scope="ocr",
    )
    tid = task["id"]
    relevant = await service.memory_create(
        project_id=pid,
        category="decisions",
        title="OCR rotation",
        body="Async OCR path is current",
        scope="ocr",
        status="active",
        source_refs=[sources[0]["source_id"]],
    )
    await service.memory_create(
        project_id=pid,
        category="decisions",
        title="Old OCR rotation",
        body="Old sync OCR path",
        scope="ocr",
        status="superseded",
    )
    await service.memory_create(
        project_id=pid,
        category="findings",
        title="Frontend",
        body="Unrelated frontend color",
        scope="frontend",
        status="active",
    )
    context = await service.context_build(
        project_id=pid,
        task_id=tid,
        query="OCR",
        budget_chars=4000,
    )
    assert sources[0]["record_id"] in context["policy_refs"]
    assert relevant["id"] in [item["id"] for item in context["selected_items"]]
    assert len(service_encoded(context)) <= 4000
    assert all(
        "Old sync" not in str(item) and "frontend" not in str(item).lower() for item in context["selected_items"]
    )
    with pytest.raises(MemoryError) as small:
        await service.context_build(project_id=pid, task_id=tid, budget_chars=100)
    assert small.value.code == "CONTEXT_BUDGET_TOO_SMALL"
    policy_file.write_text("Changed policy: review required.")
    changed = await service.context_build(project_id=pid, task_id=tid, budget_chars=4000)
    assert changed["missing_required"] == [sources[0]["record_id"]]
    assert "Mandatory: use async" not in str(changed)
    assert relevant["id"] not in [item["id"] for item in changed["selected_items"]]
    outside = tmp_path / "outside.md"
    outside.write_text("not authorized")
    (root / "outside.md").symlink_to(outside)
    with pytest.raises(MemoryError) as denied:
        await service.source_index(project_id=pid, paths=["outside.md"])
    assert denied.value.code == "ACCESS_DENIED"
    await engine.dispose()


def service_encoded(value: object) -> str:
    from project_memory.application.service import encoded

    return encoded(value)
