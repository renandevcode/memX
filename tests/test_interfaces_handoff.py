import asyncio
from pathlib import Path

import httpx
import pytest
from mcp import Client

from project_memory.application.handoff import MemoryService
from project_memory.application.service import MemoryError
from project_memory.config import Settings
from project_memory.infrastructure.db import make_engine, migrate
from project_memory.interfaces.http import create_app
from project_memory.interfaces.mcp import create_mcp


@pytest.mark.asyncio
async def test_two_clients_handoff_once_and_http_rules(tmp_path: Path) -> None:
    root = tmp_path / "ocr"
    root.mkdir()
    data_dir = tmp_path / "data"
    config = Settings(data_dir=data_dir, http_token="test-token")
    migrate(config.db_url)
    server_a = create_mcp(config)
    async with Client(server_a) as client_a:
        tools = await client_a.list_tools()
        assert "handoff_create" in {tool.name for tool in tools.tools}

        async def call(name: str, arguments: dict[str, object]) -> dict[str, object]:
            result = await client_a.call_tool(name, {"arguments": arguments})
            assert not result.is_error
            assert result.structured_content is not None
            return result.structured_content

        project = await call("project_register", {"root": str(root), "name": "OCR"})
        pid = project["id"]
        task = await call(
            "task_create",
            {
                "project_id": pid,
                "title": "OCR",
                "objective": "Fix rotated pages",
                "acceptance_criteria": ["fixture passes"],
                "scope": "ocr",
            },
        )
        tid = task["id"]
        worker_a = await call(
            "session_start",
            {
                "project_id": pid,
                "host": "client-a",
                "agent_label": "A",
                "task_id": tid,
            },
        )
        checkpoint = await call(
            "task_checkpoint",
            {
                "project_id": pid,
                "task_id": tid,
                "session_id": worker_a["id"],
                "expected_version": 1,
                "completed": [],
                "pending": ["Fix rotation"],
                "blockers": [],
                "next_action": "Inspect fixture",
                "changed_paths": [],
                "evidence_refs": [],
                "checkout_ref": {"dirty": False},
                "idempotency_key": "cp-a",
            },
        )
        handoff = await call(
            "handoff_create",
            {
                "project_id": pid,
                "task_id": tid,
                "checkpoint_id": checkpoint["id"],
                "idempotency_key": "handoff-a",
                "reason": "Continue tomorrow",
            },
        )
    # A new MCP server object models process restart against the same SQLite file.
    server_b = create_mcp(config)
    async with Client(server_b) as client_b:

        async def call_b(name: str, arguments: dict[str, object]) -> dict[str, object]:
            result = await client_b.call_tool(name, {"arguments": arguments})
            assert not result.is_error
            assert result.structured_content is not None
            return result.structured_content

        worker_b = await call_b(
            "session_start",
            {
                "project_id": pid,
                "host": "client-b",
                "agent_label": "B",
                "task_id": tid,
            },
        )
        accepted = await call_b(
            "handoff_accept",
            {
                "project_id": pid,
                "handoff_id": handoff["id"],
                "expected_version": 1,
                "session_id": worker_b["id"],
            },
        )
        assert accepted["checkpoint"]["pending"] == ["Fix rotation"]
        duplicate = await client_b.call_tool(
            "handoff_accept",
            {
                "arguments": {
                    "project_id": pid,
                    "handoff_id": handoff["id"],
                    "expected_version": 1,
                    "session_id": worker_b["id"],
                }
            },
        )
        assert duplicate.is_error
        assert "VERSION_CONFLICT" in str(duplicate.content)

    engine = make_engine(config.db_url)
    app = create_app(config, engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        request = {"schema_version": 1, "arguments": {"project_id": pid, "task_id": tid}}
        assert (await client.post("/v1/task_read", json=request)).status_code == 401
        response = await client.post("/v1/task_read", json=request, headers={"Authorization": "Bearer test-token"})
        assert response.status_code == 200
        assert response.json()["version"] == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_claims_use_database_cas(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    url = f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"
    migrate(url)
    engine_a = make_engine(url)
    engine_b = make_engine(url)
    service_a = MemoryService(engine_a)
    service_b = MemoryService(engine_b)
    pid = (await service_a.project_register(root=str(root), name="Project"))["id"]
    task = await service_a.task_create(
        project_id=pid,
        title="Task",
        objective="Do work",
        acceptance_criteria=["done"],
    )
    tid = task["id"]
    session_a = await service_a.session_start(project_id=pid, host="A", agent_label="A", task_id=tid)
    cp = await service_a.task_checkpoint(
        project_id=pid,
        task_id=tid,
        session_id=session_a["id"],
        expected_version=1,
        completed=[],
        pending=["work"],
        blockers=[],
        next_action="work",
        changed_paths=[],
        evidence_refs=[],
        checkout_ref={},
        idempotency_key="cp",
    )
    handoff = await service_a.handoff_create(
        project_id=pid,
        task_id=tid,
        checkpoint_id=cp["id"],
        idempotency_key="handoff",
        reason="Continue",
    )
    session_b = await service_b.session_start(project_id=pid, host="B", agent_label="B", task_id=tid)

    async def claim(service: MemoryService, sid: str) -> str:
        try:
            await service.handoff_accept(project_id=pid, handoff_id=handoff["id"], expected_version=1, session_id=sid)
            return "accepted"
        except MemoryError as exc:
            return exc.code

    results = await asyncio.gather(claim(service_a, session_a["id"]), claim(service_b, session_b["id"]))
    assert sorted(results) == ["VERSION_CONFLICT", "accepted"]
    await engine_a.dispose()
    await engine_b.dispose()
