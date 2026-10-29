"""Local application service. Each operation owns one short database transaction."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from project_memory.application.paths import DEFAULT_EXCLUDED_PATHS, is_excluded
from project_memory.application.storage import Session, Store, text


def new_id() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(UTC).isoformat()


def encoded(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: object) -> str:
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class MemoryError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class MemoryService:
    def __init__(self, store: Store, excluded_paths: tuple[str, ...] = DEFAULT_EXCLUDED_PATHS):
        self.store = store
        self.session_factory = store.session_factory
        self.excluded_paths = excluded_paths

    async def project_register(self, *, root: str, name: str) -> dict[str, str]:
        path = Path(root).resolve(strict=True)
        if not path.is_dir():
            raise MemoryError("INVALID_REFERENCE", "Project root must be a directory")
        if not name.strip():
            raise MemoryError("INVALID_INPUT", "Project name is required")
        project_id = new_id()
        async with self.session_factory() as session, session.begin():
            existing = (
                await session.execute(text("SELECT id FROM projects WHERE root=:root"), {"root": str(path)})
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

    async def _row(self, session: Session, table: str, entity_id: str, project_id: str) -> dict[str, object]:
        if table not in {"tasks", "sessions", "evidence", "checkpoints", "handoffs"}:
            raise ValueError("Unsupported entity")
        row = (
            (
                await session.execute(
                    text(f"SELECT * FROM {table} WHERE id=:id AND project_id=:project_id"),
                    {"id": entity_id, "project_id": project_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise MemoryError("INVALID_REFERENCE", f"{table} reference is missing from project")
        return dict(row)

    async def task_create(
        self, *, project_id: str, title: str, objective: str, acceptance_criteria: list[str], scope: str = ""
    ) -> dict[str, object]:
        if not title.strip() or not objective.strip() or not acceptance_criteria:
            raise MemoryError("INVALID_INPUT", "Task needs title, objective and acceptance criteria")
        task_id = new_id()
        async with self.session_factory() as session, session.begin():
            await self._project_exists(session, project_id)
            await session.execute(
                text(
                    "INSERT INTO tasks (id,project_id,title,objective,acceptance,scope,status,version) "
                    "VALUES (:id,:project_id,:title,:objective,:acceptance,:scope,'todo',1)"
                ),
                {
                    "id": task_id,
                    "project_id": project_id,
                    "title": title,
                    "objective": objective,
                    "acceptance": encoded(acceptance_criteria),
                    "scope": scope,
                },
            )
        return await self.task_read(project_id, task_id)

    async def _project_exists(self, session: Session, project_id: str) -> None:
        found = (
            await session.execute(text("SELECT 1 FROM projects WHERE id=:id"), {"id": project_id})
        ).scalar_one_or_none()
        if found is None:
            raise MemoryError("NOT_FOUND", "Project not found")

    async def task_read(self, project_id: str, task_id: str) -> dict[str, object]:
        async with self.session_factory() as session:
            row = await self._row(session, "tasks", task_id, project_id)
            row["acceptance_criteria"] = json.loads(str(row.pop("acceptance")))
            return row

    async def task_transition(
        self,
        *,
        project_id: str,
        task_id: str,
        expected_version: int,
        status: str,
        reason: str,
        evidence_refs: list[str] | None = None,
        human_exception: str | None = None,
    ) -> dict[str, object]:
        transitions = {
            "todo": {"in_progress", "blocked", "cancelled"},
            "in_progress": {"blocked", "in_review", "cancelled"},
            "blocked": {"in_progress", "cancelled"},
            "in_review": {"in_progress", "blocked", "done", "cancelled"},
            "done": set(),
            "cancelled": set(),
        }
        if not reason.strip() or (human_exception is not None and not human_exception.strip()):
            raise MemoryError("INVALID_INPUT", "Transition reason and human exception must be nonempty")
        async with self.session_factory() as session, session.begin():
            task = await self._row(session, "tasks", task_id, project_id)
            current = str(task["status"])
            if status not in transitions.get(current, set()):
                raise MemoryError("INVALID_INPUT", f"Cannot move task from {current} to {status}")
            if task["version"] != expected_version:
                raise MemoryError("VERSION_CONFLICT", "Task version changed")
            verified = False
            for evidence_id in evidence_refs or []:
                evidence = await self._row(session, "evidence", evidence_id, project_id)
                verified = verified or evidence["verification_status"] == "verified"
            if status == "done" and not verified and not human_exception:
                raise MemoryError("INVALID_REFERENCE", "Done requires verified evidence or explicit human exception")
            changed = await session.execute(
                text(
                    "UPDATE tasks SET status=:status,version=version+1 "
                    "WHERE id=:id AND project_id=:pid AND version=:version"
                ),
                {"status": status, "id": task_id, "pid": project_id, "version": expected_version},
            )
            if changed.rowcount != 1:
                raise MemoryError("VERSION_CONFLICT", "Task version changed")
            await session.execute(
                text(
                    "INSERT INTO audit_entries (id,project_id,operation,target_id,target_version,reason,created_at) "
                    "VALUES (:id,:pid,'task_transition',:target,:version,:reason,:at)"
                ),
                {
                    "id": new_id(),
                    "pid": project_id,
                    "target": task_id,
                    "version": expected_version + 1,
                    "reason": reason + (f"; human_exception: {human_exception}" if human_exception else ""),
                    "at": now(),
                },
            )
        return {"id": task_id, "status": status, "version": expected_version + 1}

    async def session_start(
        self,
        *,
        project_id: str,
        host: str,
        agent_label: str,
        task_id: str | None = None,
        model_label: str | None = None,
    ) -> dict[str, object]:
        if not host.strip() or not agent_label.strip():
            raise MemoryError("INVALID_INPUT", "Host and agent label are required")
        session_id = new_id()
        async with self.session_factory() as session, session.begin():
            await self._project_exists(session, project_id)
            if task_id:
                await self._row(session, "tasks", task_id, project_id)
            await session.execute(
                text(
                    "INSERT INTO sessions "
                    "(id,project_id,task_id,host,agent_label,model_label,status,started_at) "
                    "VALUES (:id,:project_id,:task_id,:host,:agent_label,:model_label,'active',:at)"
                ),
                {
                    "id": session_id,
                    "project_id": project_id,
                    "task_id": task_id,
                    "host": host,
                    "agent_label": agent_label,
                    "model_label": model_label,
                    "at": now(),
                },
            )
        return {"id": session_id, "project_id": project_id, "task_id": task_id, "host": host, "status": "active"}

    async def session_end(self, *, project_id: str, session_id: str) -> dict[str, object]:
        async with self.session_factory() as session, session.begin():
            row = await self._row(session, "sessions", session_id, project_id)
            if row["status"] != "active":
                raise MemoryError("VERSION_CONFLICT", "Session already ended")
            await session.execute(
                text("UPDATE sessions SET status='ended',ended_at=:at WHERE id=:id"),
                {"at": now(), "id": session_id},
            )
        return {"id": session_id, "status": "ended"}

    async def event_append(
        self,
        *,
        project_id: str,
        session_id: str,
        kind: str,
        payload: dict[str, object],
        idempotency_key: str,
        task_id: str | None = None,
    ) -> dict[str, object]:
        content = encoded(payload)
        if len(content.encode()) > 32768:
            raise MemoryError("INVALID_INPUT", "Event exceeds 32768 bytes")
        if not kind or not idempotency_key:
            raise MemoryError("INVALID_INPUT", "Kind and idempotency key are required")

        def contains_excluded(value: object) -> bool:
            if isinstance(value, dict):
                for key, item in value.items():
                    lowered = str(key).lower()
                    if lowered in {"password", "token", "secret", "api_key", "authorization"}:
                        return True
                    if lowered in {"path", "file", "artifact_ref"} and isinstance(item, str):
                        if is_excluded(item, self.excluded_paths):
                            return True
                    if contains_excluded(item):
                        return True
            elif isinstance(value, list):
                return any(contains_excluded(item) for item in value)
            return False

        if contains_excluded(payload):
            raise MemoryError("INVALID_INPUT", "Sensitive payload field is excluded")
        digest = fingerprint({"kind": kind, "payload": payload, "task_id": task_id})
        async with self.session_factory() as session, session.begin():
            owner = await self._row(session, "sessions", session_id, project_id)
            if owner["status"] != "active":
                raise MemoryError("VERSION_CONFLICT", "Session is not active")
            if task_id:
                await self._row(session, "tasks", task_id, project_id)
            prior = (
                (
                    await session.execute(
                        text("SELECT * FROM events WHERE session_id=:sid AND idempotency_key=:key"),
                        {"sid": session_id, "key": idempotency_key},
                    )
                )
                .mappings()
                .first()
            )
            if prior:
                if prior["fingerprint"] != digest:
                    raise MemoryError("IDEMPOTENCY_CONFLICT", "Event key reused with different content")
                return {"id": prior["id"], "sequence": prior["sequence"]}
            sequence = (
                await session.execute(
                    text("SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE session_id=:sid"),
                    {"sid": session_id},
                )
            ).scalar_one()
            event_id = new_id()
            await session.execute(
                text(
                    "INSERT INTO events "
                    "(id,project_id,session_id,task_id,idempotency_key,fingerprint,sequence,kind,payload,captured_at) "
                    "VALUES (:id,:pid,:sid,:tid,:key,:fp,:seq,:kind,:payload,:at)"
                ),
                {
                    "id": event_id,
                    "pid": project_id,
                    "sid": session_id,
                    "tid": task_id,
                    "key": idempotency_key,
                    "fp": digest,
                    "seq": sequence,
                    "kind": kind,
                    "payload": content,
                    "at": now(),
                },
            )
        return {"id": event_id, "sequence": sequence}

    async def evidence_create(
        self,
        *,
        project_id: str,
        kind: str,
        artifact_ref: str,
        content_hash: str,
        checkout_ref: dict[str, object],
        verification_status: str = "unverified",
    ) -> dict[str, object]:
        if verification_status != "unverified":
            raise MemoryError("INVALID_INPUT", "Explicit client evidence remains unverified")
        project = await self.project_read(project_id)
        root = Path(project["root"])
        if is_excluded(artifact_ref, self.excluded_paths):
            raise MemoryError("ACCESS_DENIED", "Artifact path is excluded or outside project")
        try:
            artifact = (root / artifact_ref).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise MemoryError("INVALID_REFERENCE", "Artifact path is unavailable") from exc
        if (
            not artifact.is_relative_to(root)
            or not artifact.is_file()
            or is_excluded(
                artifact.relative_to(root) if artifact.is_relative_to(root) else artifact, self.excluded_paths
            )
        ):
            raise MemoryError("ACCESS_DENIED", "Artifact path is excluded or outside project")
        data = await asyncio.to_thread(artifact.read_bytes)
        if len(data) > 65536:
            raise MemoryError("INVALID_INPUT", "Artifact exceeds 65536 bytes")
        if hashlib.sha256(data).hexdigest() != content_hash:
            raise MemoryError("INVALID_INPUT", "Artifact hash mismatch")
        evidence_id = new_id()
        async with self.session_factory() as session, session.begin():
            await self._project_exists(session, project_id)
            await session.execute(
                text(
                    "INSERT INTO evidence "
                    "(id,project_id,kind,artifact_ref,content_hash,checkout_ref,verification_status,observed_at) "
                    "VALUES (:id,:pid,:kind,:ref,:hash,:checkout,:status,:at)"
                ),
                {
                    "id": evidence_id,
                    "pid": project_id,
                    "kind": kind,
                    "ref": artifact_ref,
                    "hash": content_hash,
                    "checkout": encoded(checkout_ref),
                    "status": verification_status,
                    "at": now(),
                },
            )
        return {"id": evidence_id, "verification_status": verification_status}

    async def task_checkpoint(
        self,
        *,
        project_id: str,
        task_id: str,
        session_id: str,
        expected_version: int,
        completed: list[str],
        pending: list[str],
        blockers: list[str],
        next_action: str,
        changed_paths: list[str],
        evidence_refs: list[str],
        checkout_ref: dict[str, object],
        idempotency_key: str,
        fail_after_update: bool = False,
    ) -> dict[str, object]:
        body = {
            "session_id": session_id,
            "expected_version": expected_version,
            "completed": completed,
            "pending": pending,
            "blockers": blockers,
            "next_action": next_action,
            "changed_paths": changed_paths,
            "evidence_refs": evidence_refs,
            "checkout_ref": checkout_ref,
        }
        digest = fingerprint(body)
        project = await self.project_read(project_id)
        root = Path(project["root"])
        for relative in changed_paths:
            if is_excluded(relative, self.excluded_paths):
                raise MemoryError("ACCESS_DENIED", "Changed path is excluded or outside project")
            path = (root / relative).resolve()
            if (
                Path(relative).is_absolute()
                or not path.is_relative_to(root)
                or is_excluded(path.relative_to(root) if path.is_relative_to(root) else path, self.excluded_paths)
            ):
                raise MemoryError("ACCESS_DENIED", "Changed path is excluded or outside project")
        async with self.session_factory() as session, session.begin():
            task = await self._row(session, "tasks", task_id, project_id)
            if task["status"] not in {"todo", "in_progress", "blocked"}:
                raise MemoryError("INVALID_INPUT", "Task status does not allow a checkpoint")
            owner = await self._row(session, "sessions", session_id, project_id)
            if owner["task_id"] not in (None, task_id):
                raise MemoryError("INVALID_REFERENCE", "Session belongs to another task")
            prior = (
                (
                    await session.execute(
                        text(
                            "SELECT id,task_version,event_watermark,fingerprint FROM checkpoints "
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
                    raise MemoryError("IDEMPOTENCY_CONFLICT", "Checkpoint key reused")
                return {
                    "id": prior["id"],
                    "task_version": prior["task_version"],
                    "event_watermark": prior["event_watermark"],
                }
            if task["version"] != expected_version:
                raise MemoryError("VERSION_CONFLICT", "Task version changed")
            for ref in evidence_refs:
                await self._row(session, "evidence", ref, project_id)
            watermark = (
                await session.execute(
                    text("SELECT COALESCE(MAX(sequence),0) FROM events WHERE session_id=:sid"),
                    {"sid": session_id},
                )
            ).scalar_one()
            result = await session.execute(
                text(
                    "UPDATE tasks SET version=version+1,status='in_progress' "
                    "WHERE id=:tid AND project_id=:pid AND version=:version"
                ),
                {"tid": task_id, "pid": project_id, "version": expected_version},
            )
            if result.rowcount != 1:
                raise MemoryError("VERSION_CONFLICT", "Task version changed")
            if fail_after_update:
                raise RuntimeError("Injected transaction failure")
            checkpoint_id = new_id()
            await session.execute(
                text(
                    "INSERT INTO checkpoints "
                    "(id,project_id,task_id,task_version,session_id,idempotency_key,fingerprint,"
                    "completed,pending,blockers,next_action,changed_paths,evidence_refs,checkout_ref,"
                    "event_watermark,created_at) VALUES "
                    "(:id,:pid,:tid,:version,:sid,:key,:fp,:completed,:pending,:blockers,:next_action,"
                    ":changed_paths,:evidence_refs,:checkout_ref,:watermark,:at)"
                ),
                {
                    "id": checkpoint_id,
                    "pid": project_id,
                    "tid": task_id,
                    "version": expected_version + 1,
                    "sid": session_id,
                    "key": idempotency_key,
                    "fp": digest,
                    "completed": encoded(completed),
                    "pending": encoded(pending),
                    "blockers": encoded(blockers),
                    "next_action": next_action,
                    "changed_paths": encoded(changed_paths),
                    "evidence_refs": encoded(evidence_refs),
                    "checkout_ref": encoded(checkout_ref),
                    "watermark": watermark,
                    "at": now(),
                },
            )
        return {"id": checkpoint_id, "task_version": expected_version + 1, "event_watermark": watermark}

    async def checkpoint_read(self, project_id: str, checkpoint_id: str) -> dict[str, object]:
        async with self.session_factory() as session:
            row = await self._row(session, "checkpoints", checkpoint_id, project_id)
            for key in ("completed", "pending", "blockers", "changed_paths", "evidence_refs", "checkout_ref"):
                row[key] = json.loads(str(row[key]))
            return row
