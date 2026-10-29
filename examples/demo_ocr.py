"""End-to-end OCR fixture with two independent MCP stdio client processes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters


async def invoke(client: Client, operation: str, **arguments: Any) -> Any:
    result = await client.call_tool(operation, {"arguments": arguments})
    if result.is_error or result.structured_content is None:
        raise RuntimeError(f"{operation}: {result.content}")
    structured = result.structured_content
    return structured.get("result", structured)


async def run_demo() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="memx-ocr-") as temporary:
        base = Path(temporary)
        root = base / "ocr-project"
        root.mkdir()
        data_dir = base / "data"
        policy = root / "POLICY.md"
        policy.write_text("Mandatory OCR policy: use asynchronous processing.")
        artifact = root / "failed-test.txt"
        artifact.write_text("Rotated page fixture failed: orientation mismatch.")
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "project_memory.interfaces.mcp"],
            env={"MEMX_DATA_DIR": str(data_dir)},
        )

        async with Client(params) as client_a:
            project = await invoke(client_a, "project_register", root=str(root), name="OCR fixture")
            pid = project["id"]
            source = (
                await invoke(
                    client_a,
                    "source_index",
                    project_id=pid,
                    paths=["POLICY.md"],
                    kind="policies",
                    scope="ocr",
                )
            )["items"][0]
            task = await invoke(
                client_a,
                "task_create",
                project_id=pid,
                title="Fix OCR rotation",
                objective="Handle rotated pages",
                acceptance_criteria=["rotated fixture passes"],
                scope="ocr",
            )
            tid = task["id"]
            session_a = await invoke(
                client_a,
                "session_start",
                project_id=pid,
                host="demo-client-a",
                agent_label="A",
                task_id=tid,
            )
            sid_a = session_a["id"]
            await invoke(
                client_a,
                "event_append",
                project_id=pid,
                session_id=sid_a,
                task_id=tid,
                kind="test_failed",
                payload={"summary": "Rotated fixture failed", "provenance": "agent_reported"},
                idempotency_key="ocr-event-1",
            )
            evidence = await invoke(
                client_a,
                "evidence_create",
                project_id=pid,
                kind="test_output",
                artifact_ref="failed-test.txt",
                content_hash=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                checkout_ref={"commit": "synthetic-fixture", "dirty": True},
            )
            active = await invoke(
                client_a,
                "memory_create",
                project_id=pid,
                category="decisions",
                title="OCR rotation strategy",
                body="Use async page workers for current rotation handling.",
                scope="ocr",
                source_refs=[source["source_id"]],
                status="active",
            )
            await invoke(
                client_a,
                "memory_create",
                project_id=pid,
                category="decisions",
                title="Old OCR rotation strategy",
                body="Use synchronous workers for OCR rotation.",
                scope="ocr",
                status="superseded",
            )
            await invoke(
                client_a,
                "memory_create",
                project_id=pid,
                category="findings",
                title="Frontend theme",
                body="Blue button styles",
                scope="frontend",
                status="active",
            )
            checkpoint_a = await invoke(
                client_a,
                "task_checkpoint",
                project_id=pid,
                task_id=tid,
                session_id=sid_a,
                expected_version=1,
                completed=["Page detection implemented"],
                pending=["Fix rotated fixture"],
                blockers=[],
                next_action="Inspect orientation",
                changed_paths=["src/ocr.py"],
                evidence_refs=[evidence["id"]],
                checkout_ref={"commit": "synthetic-fixture", "dirty": True},
                idempotency_key="ocr-cp-a",
            )
            handoff = await invoke(
                client_a,
                "handoff_create",
                project_id=pid,
                task_id=tid,
                checkpoint_id=checkpoint_a["id"],
                idempotency_key="ocr-handoff",
                reason="Continue with another client",
            )
            await invoke(client_a, "session_end", project_id=pid, session_id=sid_a)

        # The prior MCP server subprocess is gone. This starts a fresh process.
        async with Client(params) as client_b:
            session_b = await invoke(
                client_b,
                "session_start",
                project_id=pid,
                host="demo-client-b",
                agent_label="B",
                task_id=tid,
            )
            accepted = await invoke(
                client_b,
                "handoff_accept",
                project_id=pid,
                handoff_id=handoff["id"],
                expected_version=1,
                session_id=session_b["id"],
            )
            assert accepted["checkpoint"]["pending"] == ["Fix rotated fixture"]
            context = await invoke(
                client_b,
                "context_build",
                project_id=pid,
                task_id=tid,
                query="OCR rotation",
                budget_chars=4000,
                checkout_ref={"commit": "synthetic-fixture", "dirty": True},
            )
            selected = context["selected_items"]
            assert source["record_id"] in context["policy_refs"]
            assert active["id"] in [item["id"] for item in selected]
            assert "Fix rotated fixture" in str(context["task_state"])
            assert not any("Use synchronous workers" in str(item) or "Blue button" in str(item) for item in selected)
            assert context["usage"]["count"] <= 4000
            checkpoint_b = await invoke(
                client_b,
                "task_checkpoint",
                project_id=pid,
                task_id=tid,
                session_id=session_b["id"],
                expected_version=2,
                completed=["Investigated orientation"],
                pending=["Run rotated fixture"],
                blockers=[],
                next_action="Run fixture",
                changed_paths=["src/ocr.py"],
                evidence_refs=[evidence["id"]],
                checkout_ref={"commit": "synthetic-fixture", "dirty": True},
                idempotency_key="ocr-cp-b",
            )
            stale = await client_b.call_tool(
                "task_checkpoint",
                {
                    "arguments": {
                        "project_id": pid,
                        "task_id": tid,
                        "session_id": sid_a,
                        "expected_version": 2,
                        "completed": [],
                        "pending": [],
                        "blockers": [],
                        "next_action": "Stale write",
                        "changed_paths": [],
                        "evidence_refs": [],
                        "checkout_ref": {},
                        "idempotency_key": "ocr-stale-a",
                    }
                },
            )
            assert stale.is_error and "VERSION_CONFLICT" in str(stale.content)
            await invoke(
                client_b,
                "memory_delete",
                project_id=pid,
                record_id=active["id"],
                expected_version=1,
                reason="Exercise deletion",
            )
            await invoke(client_b, "memory_reindex", project_id=pid)
            results = await invoke(
                client_b,
                "memory_search",
                project_id=pid,
                query="async",
                scope="ocr",
            )
            assert active["id"] not in [item["id"] for item in results["items"]]
            policy.write_text("Changed policy: review async scheduling.")
            changed = await invoke(
                client_b,
                "context_build",
                project_id=pid,
                task_id=tid,
                query="OCR",
                budget_chars=4000,
            )
            assert source["record_id"] in changed["missing_required"]
            assert "Mandatory OCR policy" not in str(changed)
            return {
                "status": "passed",
                "clients": "2 MCP stdio subprocesses",
                "task_id": tid,
                "checkpoint_version": checkpoint_b["task_version"],
                "context_count": context["usage"]["count"],
                "context_budget": context["usage"]["budget"],
                "policy_changed_warning": changed["warnings"],
                "evidence_status": evidence["verification_status"],
            }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_demo()), ensure_ascii=False))
