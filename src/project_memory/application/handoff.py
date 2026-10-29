"""Cooperative handoff between external clients."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult

from project_memory.application.memory import MemoryService as MemoryBase
from project_memory.application.service import MemoryError, fingerprint, new_id, now


class MemoryService(MemoryBase):
    async def handoff_create(
        self, *, project_id: str, task_id: str, checkpoint_id: str, idempotency_key: str, reason: str
    ) -> dict[str, object]:
        if not reason.strip() or not idempotency_key:
            raise MemoryError("INVALID_INPUT", "Reason and idempotency key are required")
        digest = fingerprint({"checkpoint_id": checkpoint_id, "reason": reason})
        async with self.session_factory() as session, session.begin():
            task = await self._row(session, "tasks", task_id, project_id)
            checkpoint = await self._row(session, "checkpoints", checkpoint_id, project_id)
            if checkpoint["task_id"] != task_id or checkpoint["task_version"] != task["version"]:
                raise MemoryError("INVALID_REFERENCE", "Checkpoint is not the latest task state")
            prior = (
                (
                    await session.execute(
                        text(
                            "SELECT id,state,version,fingerprint FROM handoffs "
                            "WHERE task_id=:tid AND idempotency_key=:key"
                        ),
                        {"tid": task_id, "key": idempotency_key},
                    )
                )
                .mappings()
                .first()
            )
            if prior:
                if prior["fingerprint"] != digest:
                    raise MemoryError("IDEMPOTENCY_CONFLICT", "Handoff key reused")
                return {"id": prior["id"], "state": prior["state"], "version": prior["version"]}
            handoff_id = new_id()
            await session.execute(
                text(
                    "INSERT INTO handoffs "
                    "(id,project_id,task_id,checkpoint_id,idempotency_key,fingerprint,state,version,created_at) "
                    "VALUES (:id,:pid,:tid,:cp,:key,:fp,'open',1,:at)"
                ),
                {
                    "id": handoff_id,
                    "pid": project_id,
                    "tid": task_id,
                    "cp": checkpoint_id,
                    "key": idempotency_key,
                    "fp": digest,
                    "at": now(),
                },
            )
        return {"id": handoff_id, "state": "open", "version": 1}

    async def handoff_accept(
        self, *, project_id: str, handoff_id: str, expected_version: int, session_id: str
    ) -> dict[str, object]:
        async with self.session_factory() as session, session.begin():
            handoff = await self._row(session, "handoffs", handoff_id, project_id)
            owner = await self._row(session, "sessions", session_id, project_id)
            if owner["status"] != "active" or owner["task_id"] not in (None, handoff["task_id"]):
                raise MemoryError("INVALID_REFERENCE", "Claiming session cannot accept this task")
            changed = await session.execute(
                text(
                    "UPDATE handoffs SET state='accepted',claimed_by=:sid,version=version+1 "
                    "WHERE id=:id AND project_id=:pid AND version=:version AND state='open'"
                ),
                {"sid": session_id, "id": handoff_id, "pid": project_id, "version": expected_version},
            )
            if cast(CursorResult[Any], changed).rowcount != 1:
                raise MemoryError("VERSION_CONFLICT", "Handoff was already accepted or changed")
            checkpoint_id = str(handoff["checkpoint_id"])
            task_id = str(handoff["task_id"])
        checkpoint = await self.checkpoint_read(project_id, checkpoint_id)
        return {
            "id": handoff_id,
            "state": "accepted",
            "version": expected_version + 1,
            "task_id": task_id,
            "checkpoint": checkpoint,
        }
