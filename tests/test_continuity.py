import hashlib
from pathlib import Path

import pytest

from project_memory.application.service import MemoryError, MemoryService
from project_memory.infrastructure.db import make_engine, migrate


@pytest.mark.asyncio
async def test_task_transitions_require_version_and_done_justification(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"
    migrate(url)
    engine = make_engine(url)
    service = MemoryService(engine)
    pid = (await service.project_register(root=str(tmp_path), name="Project"))["id"]
    task = await service.task_create(project_id=pid, title="Task", objective="Finish", acceptance_criteria=["reviewed"])
    tid = task["id"]
    progress = await service.task_transition(
        project_id=pid, task_id=tid, expected_version=1, status="in_progress", reason="Started"
    )
    assert progress["version"] == 2
    with pytest.raises(MemoryError) as stale:
        await service.task_transition(
            project_id=pid, task_id=tid, expected_version=1, status="in_review", reason="Stale"
        )
    assert stale.value.code == "VERSION_CONFLICT"
    await service.task_transition(project_id=pid, task_id=tid, expected_version=2, status="in_review", reason="Review")
    with pytest.raises(MemoryError) as unproven:
        await service.task_transition(project_id=pid, task_id=tid, expected_version=3, status="done", reason="Done")
    assert unproven.value.code == "INVALID_REFERENCE"
    assert (await service.task_read(pid, tid))["version"] == 3
    done = await service.task_transition(
        project_id=pid,
        task_id=tid,
        expected_version=3,
        status="done",
        reason="Accepted by operator",
        human_exception="The operator explicitly accepted this fixture",
    )
    assert done == {"id": tid, "status": "done", "version": 4}
    await engine.dispose()


@pytest.mark.asyncio
async def test_checkpoint_is_atomic_idempotent_and_survives_restart(tmp_path: Path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'mem.sqlite3'}"
    migrate(db_url)
    engine = make_engine(db_url)
    service = MemoryService(engine)
    project = await service.project_register(root=str(tmp_path), name="OCR")
    pid = project["id"]
    task = await service.task_create(
        project_id=pid,
        title="OCR",
        objective="Detect rotated pages",
        acceptance_criteria=["rotated fixture passes"],
        scope="ocr",
    )
    tid = str(task["id"])
    worker = await service.session_start(project_id=pid, host="test", agent_label="A", task_id=tid)
    sid = str(worker["id"])
    event = await service.event_append(
        project_id=pid,
        session_id=sid,
        task_id=tid,
        kind="test_failed",
        payload={"summary": "rotated fixture failed"},
        idempotency_key="event-1",
    )
    assert event == await service.event_append(
        project_id=pid,
        session_id=sid,
        task_id=tid,
        kind="test_failed",
        payload={"summary": "rotated fixture failed"},
        idempotency_key="event-1",
    )
    with pytest.raises(MemoryError) as conflict:
        await service.event_append(
            project_id=pid,
            session_id=sid,
            task_id=tid,
            kind="test_passed",
            payload={},
            idempotency_key="event-1",
        )
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"
    artifact = tmp_path / "rotated.txt"
    artifact.write_text("rotated fixture failed")
    evidence = await service.evidence_create(
        project_id=pid,
        kind="test_output",
        artifact_ref="rotated.txt",
        content_hash=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        checkout_ref={"dirty": True},
    )
    args = dict(
        project_id=pid,
        task_id=tid,
        session_id=sid,
        expected_version=1,
        completed=["Implemented page detection"],
        pending=["Fix rotated fixture"],
        blockers=[],
        next_action="Inspect rotation",
        changed_paths=["src/ocr.py"],
        evidence_refs=[evidence["id"]],
        checkout_ref={"dirty": True},
        idempotency_key="cp-1",
    )
    with pytest.raises(RuntimeError, match="Injected"):
        await service.task_checkpoint(**args, fail_after_update=True)
    assert (await service.task_read(pid, tid))["version"] == 1
    checkpoint = await service.task_checkpoint(**args)
    assert checkpoint == await service.task_checkpoint(**args)
    with pytest.raises(MemoryError) as stale:
        await service.task_checkpoint(**{**args, "idempotency_key": "cp-2"})
    assert stale.value.code == "VERSION_CONFLICT"
    assert (await service.checkpoint_read(pid, str(checkpoint["id"])))["event_watermark"] == 1
    await service.session_end(project_id=pid, session_id=sid)
    await engine.dispose()

    reopened = make_engine(db_url)
    resumed = MemoryService(reopened)
    assert (await resumed.task_read(pid, tid))["version"] == 2
    assert (await resumed.checkpoint_read(pid, str(checkpoint["id"])))["pending"] == ["Fix rotated fixture"]
    await reopened.dispose()


@pytest.mark.asyncio
async def test_project_scoped_references(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    url = f"sqlite+aiosqlite:///{tmp_path / 'mem.sqlite3'}"
    migrate(url)
    engine = make_engine(url)
    service = MemoryService(engine)
    a = await service.project_register(root=str(first), name="A")
    b = await service.project_register(root=str(second), name="B")
    task = await service.task_create(
        project_id=a["id"],
        title="Task",
        objective="Work",
        acceptance_criteria=["done"],
    )
    with pytest.raises(MemoryError) as error:
        await service.session_start(project_id=b["id"], host="test", agent_label="B", task_id=str(task["id"]))
    assert error.value.code == "INVALID_REFERENCE"
    await engine.dispose()
