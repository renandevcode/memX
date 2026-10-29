"""Versioned records, explicit repository sources, FTS5 search and bounded context."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from project_memory.application.paths import is_excluded
from project_memory.application.service import (
    MemoryError,
    encoded,
    new_id,
    now,
)
from project_memory.application.service import (
    MemoryService as ContinuityService,
)
from project_memory.application.storage import Session, text

CATEGORIES = {"policies", "project_map", "decisions", "findings", "task_state", "session_log", "evidence"}
STATUSES = {"proposed", "active", "superseded", "archived"}
RELATIONS = {"depends_on", "governed_by", "supported_by", "supersedes", "affects", "contradicts"}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MemoryService(ContinuityService):
    async def _record(self, session: Session, project_id: str, record_id: str) -> dict[str, Any]:
        row = (
            (
                await session.execute(
                    text("SELECT * FROM memory_records WHERE id=:id AND project_id=:pid AND deleted_at IS NULL"),
                    {"id": record_id, "pid": project_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise MemoryError("NOT_FOUND", "Memory record not found in project")
        return dict(row)

    async def _validate_refs(self, session: Session, project_id: str, refs: list[str]) -> None:
        for ref in refs:
            found = (
                await session.execute(
                    text(
                        "SELECT 1 FROM source_documents WHERE id=:id AND project_id=:pid "
                        "UNION SELECT 1 FROM evidence WHERE id=:id AND project_id=:pid "
                        "UNION SELECT 1 FROM memory_records WHERE id=:id AND project_id=:pid AND deleted_at IS NULL"
                    ),
                    {"id": ref, "pid": project_id},
                )
            ).first()
            if found is None:
                raise MemoryError("INVALID_REFERENCE", "Source reference is missing from project")

    async def _index_fts(self, session: Session, record_id: str, title: str, body: str) -> None:
        await session.execute(text("DELETE FROM memory_fts WHERE record_id=:id"), {"id": record_id})
        await session.execute(
            text("INSERT INTO memory_fts (record_id,title,body) VALUES (:id,:title,:body)"),
            {"id": record_id, "title": title, "body": body},
        )

    async def memory_create(
        self,
        *,
        project_id: str,
        category: str,
        title: str,
        body: str,
        scope: str = "",
        source_refs: list[str] | None = None,
        valid_for: dict[str, object] | None = None,
        status: str = "proposed",
    ) -> dict[str, object]:
        if category not in CATEGORIES or status not in STATUSES or category == "policies":
            raise MemoryError("INVALID_INPUT", "Invalid category/status or policy must be a repo source")
        if not title.strip() or not body.strip():
            raise MemoryError("INVALID_INPUT", "Title and body are required")
        refs = source_refs or []
        record_id = new_id()
        async with self.session_factory() as session, session.begin():
            await self._project_exists(session, project_id)
            await self._validate_refs(session, project_id, refs)
            await session.execute(
                text(
                    "INSERT INTO memory_records "
                    "(id,project_id,category,scope,status,source_kind,current_version,visibility) "
                    "VALUES (:id,:pid,:category,:scope,:status,'database_record',1,'local')"
                ),
                {"id": record_id, "pid": project_id, "category": category, "scope": scope, "status": status},
            )
            await session.execute(
                text(
                    "INSERT INTO memory_versions "
                    "(record_id,version,title,body,source_refs,valid_for,created_at,actor_id,reason) "
                    "VALUES (:id,1,:title,:body,:refs,:valid_for,:at,'local_operator','create')"
                ),
                {
                    "id": record_id,
                    "title": title,
                    "body": body,
                    "refs": encoded(refs),
                    "valid_for": encoded(valid_for or {}),
                    "at": now(),
                },
            )
            await self._index_fts(session, record_id, title, body)
        return {"id": record_id, "version": 1, "status": status}

    async def memory_read(self, project_id: str, record_id: str, version: int | None = None) -> dict[str, object]:
        async with self.session_factory() as session:
            record = await self._record(session, project_id, record_id)
            selected = version or record["current_version"]
            row = (
                (
                    await session.execute(
                        text("SELECT * FROM memory_versions WHERE record_id=:id AND version=:version"),
                        {"id": record_id, "version": selected},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise MemoryError("NOT_FOUND", "Memory version not found")
            item = dict(row)
            item["source_refs"] = json.loads(item["source_refs"])
            item["valid_for"] = json.loads(item["valid_for"])
            return {**record, **item}

    async def memory_update(
        self,
        *,
        project_id: str,
        record_id: str,
        expected_version: int,
        title: str,
        body: str,
        reason: str,
        source_refs: list[str] | None = None,
        valid_for: dict[str, object] | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        if not reason.strip() or not title.strip() or not body.strip():
            raise MemoryError("INVALID_INPUT", "Reason, title and body are required")
        if status is not None and status not in STATUSES:
            raise MemoryError("INVALID_INPUT", "Invalid status")
        refs = source_refs or []
        async with self.session_factory() as session, session.begin():
            record = await self._record(session, project_id, record_id)
            if record["source_kind"] != "database_record":
                raise MemoryError("SOURCE_READ_ONLY", "Edit repository source and reindex")
            await self._validate_refs(session, project_id, refs)
            changed = await session.execute(
                text(
                    "UPDATE memory_records SET current_version=current_version+1,status=:status "
                    "WHERE id=:id AND project_id=:pid AND current_version=:version AND deleted_at IS NULL"
                ),
                {"id": record_id, "pid": project_id, "version": expected_version, "status": status or record["status"]},
            )
            if changed.rowcount != 1:
                raise MemoryError("VERSION_CONFLICT", "Memory version changed")
            await session.execute(
                text(
                    "INSERT INTO memory_versions "
                    "(record_id,version,title,body,source_refs,valid_for,created_at,actor_id,reason) "
                    "VALUES (:id,:version,:title,:body,:refs,:valid_for,:at,'local_operator',:reason)"
                ),
                {
                    "id": record_id,
                    "version": expected_version + 1,
                    "title": title,
                    "body": body,
                    "refs": encoded(refs),
                    "valid_for": encoded(valid_for or {}),
                    "at": now(),
                    "reason": reason,
                },
            )
            await self._index_fts(session, record_id, title, body)
        return {"id": record_id, "version": expected_version + 1, "status": status or record["status"]}

    async def memory_archive(
        self, *, project_id: str, record_id: str, expected_version: int, reason: str
    ) -> dict[str, object]:
        previous = await self.memory_read(project_id, record_id)
        return await self.memory_update(
            project_id=project_id,
            record_id=record_id,
            expected_version=expected_version,
            title=str(previous["title"]),
            body=str(previous["body"]),
            reason=reason,
            source_refs=cast(list[str], previous["source_refs"]),
            valid_for=cast(dict[str, object], previous["valid_for"]),
            status="archived",
        )

    async def memory_delete(
        self, *, project_id: str, record_id: str, expected_version: int, reason: str
    ) -> dict[str, object]:
        if not reason.strip():
            raise MemoryError("INVALID_INPUT", "Deletion reason is required")
        async with self.session_factory() as session, session.begin():
            record = await self._record(session, project_id, record_id)
            if record["source_kind"] != "database_record":
                raise MemoryError("SOURCE_READ_ONLY", "Delete repository source in Git")
            changed = await session.execute(
                text(
                    "UPDATE memory_records SET deleted_at=:at,status='archived' "
                    "WHERE id=:id AND project_id=:pid AND current_version=:version AND deleted_at IS NULL"
                ),
                {"id": record_id, "pid": project_id, "version": expected_version, "at": now()},
            )
            if changed.rowcount != 1:
                raise MemoryError("VERSION_CONFLICT", "Memory version changed")
            await session.execute(text("DELETE FROM memory_fts WHERE record_id=:id"), {"id": record_id})
            await session.execute(text("DELETE FROM memory_versions WHERE record_id=:id"), {"id": record_id})
            await session.execute(
                text(
                    "INSERT INTO audit_entries (id,project_id,operation,target_id,target_version,reason,created_at) "
                    "VALUES (:id,:pid,'delete',:target,:version,:reason,:at)"
                ),
                {
                    "id": new_id(),
                    "pid": project_id,
                    "target": record_id,
                    "version": expected_version,
                    "reason": reason,
                    "at": now(),
                },
            )
        return {
            "id": record_id,
            "deleted": True,
            "scope": ["database_versions", "fts_index"],
            "excluded": ["backups", "git_history", "external_artifacts"],
        }

    async def relation_create(
        self, *, project_id: str, source_id: str, target_id: str, relation_type: str
    ) -> dict[str, object]:
        if relation_type not in RELATIONS:
            raise MemoryError("INVALID_INPUT", "Unknown relation type")
        relation_id = new_id()
        async with self.session_factory() as session, session.begin():
            await self._record(session, project_id, source_id)
            await self._record(session, project_id, target_id)
            await session.execute(
                text(
                    "INSERT INTO relations (id,project_id,source_id,target_id,relation_type,origin) "
                    "VALUES (:id,:pid,:source,:target,:kind,'explicit')"
                ),
                {"id": relation_id, "pid": project_id, "source": source_id, "target": target_id, "kind": relation_type},
            )
        return {"id": relation_id, "relation_type": relation_type}

    async def source_index(
        self, *, project_id: str, paths: list[str], kind: str = "policies", scope: str = ""
    ) -> list[dict[str, object]]:
        if kind not in {"policies", "decisions", "project_map"}:
            raise MemoryError("INVALID_INPUT", "Invalid source kind")
        project = await self.project_read(project_id)
        root = Path(project["root"])
        prepared: list[tuple[str, str, str]] = []
        for relative in paths:
            if is_excluded(relative, self.excluded_paths):
                raise MemoryError("ACCESS_DENIED", "Source path is excluded or outside project")
            try:
                path = (root / relative).resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise MemoryError("INVALID_REFERENCE", "Source path is unavailable") from exc
            if not path.is_relative_to(root) or is_excluded(
                path.relative_to(root) if path.is_relative_to(root) else path, self.excluded_paths
            ):
                raise MemoryError("ACCESS_DENIED", "Source path is excluded or outside project")
            if not path.is_file():
                raise MemoryError("INVALID_REFERENCE", "Source is not a regular file")
            data = await asyncio.to_thread(path.read_bytes)
            if len(data) > 65536:
                raise MemoryError("INVALID_INPUT", "Source exceeds 65536 bytes")
            try:
                body = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MemoryError("INVALID_INPUT", "Source must be UTF-8 text") from exc
            prepared.append((str(path.relative_to(root)), body, _hash(data)))
        results: list[dict[str, object]] = []
        async with self.session_factory() as session, session.begin():
            for relative, body, digest in prepared:
                prior = (
                    (
                        await session.execute(
                            text(
                                "SELECT d.id,d.content_hash,r.id AS record_id,r.current_version "
                                "FROM source_documents d JOIN memory_records r ON r.source_document_id=d.id "
                                "WHERE d.project_id=:pid AND d.relative_path=:path"
                            ),
                            {"pid": project_id, "path": relative},
                        )
                    )
                    .mappings()
                    .first()
                )
                if prior and prior["content_hash"] == digest:
                    results.append(
                        {
                            "source_id": prior["id"],
                            "record_id": prior["record_id"],
                            "version": prior["current_version"],
                            "content_hash": digest,
                        }
                    )
                    continue
                source_id = str(prior["id"]) if prior else new_id()
                record_id = str(prior["record_id"]) if prior else new_id()
                version = int(prior["current_version"]) + 1 if prior else 1
                if prior:
                    await session.execute(
                        text(
                            "UPDATE source_documents SET content_hash=:hash,indexed_at=:at,kind=:kind,scope=:scope "
                            "WHERE id=:id"
                        ),
                        {"hash": digest, "at": now(), "kind": kind, "scope": scope, "id": source_id},
                    )
                    await session.execute(
                        text(
                            "UPDATE memory_records SET current_version=:version,category=:kind,scope=:scope "
                            "WHERE id=:id"
                        ),
                        {"version": version, "kind": kind, "scope": scope, "id": record_id},
                    )
                else:
                    await session.execute(
                        text(
                            "INSERT INTO source_documents "
                            "(id,project_id,relative_path,content_hash,kind,scope,indexed_at) "
                            "VALUES (:id,:pid,:path,:hash,:kind,:scope,:at)"
                        ),
                        {
                            "id": source_id,
                            "pid": project_id,
                            "path": relative,
                            "hash": digest,
                            "kind": kind,
                            "scope": scope,
                            "at": now(),
                        },
                    )
                    await session.execute(
                        text(
                            "INSERT INTO memory_records "
                            "(id,project_id,category,scope,status,source_kind,source_document_id,"
                            "current_version,visibility) "
                            "VALUES (:id,:pid,:kind,:scope,'active','repo_document',:source,1,'local')"
                        ),
                        {"id": record_id, "pid": project_id, "kind": kind, "scope": scope, "source": source_id},
                    )
                await session.execute(
                    text(
                        "INSERT INTO memory_versions "
                        "(record_id,version,title,body,source_refs,valid_for,created_at,actor_id,reason) "
                        "VALUES (:id,:version,:title,:body,:refs,:valid_for,:at,'local_operator','source_index')"
                    ),
                    {
                        "id": record_id,
                        "version": version,
                        "title": relative,
                        "body": body,
                        "refs": encoded([source_id]),
                        "valid_for": encoded({"content_hash": digest}),
                        "at": now(),
                    },
                )
                await self._index_fts(session, record_id, relative, body)
                results.append(
                    {"source_id": source_id, "record_id": record_id, "version": version, "content_hash": digest}
                )
        return results

    async def memory_search(
        self,
        *,
        project_id: str,
        query: str = "",
        scope: str | None = None,
        category: str | None = None,
        include_history: bool = False,
        cursor: int = 0,
        limit: int = 20,
    ) -> dict[str, object]:
        if limit < 1 or limit > 100 or cursor < 0:
            raise MemoryError("INVALID_INPUT", "Invalid pagination")
        terms = re.findall(r"\w+", query, re.UNICODE)
        expression = " AND ".join(f'"{term}"' for term in terms)
        clauses = ["r.project_id=:pid", "r.deleted_at IS NULL"]
        if not include_history:
            clauses.append("r.status='active'")
        if scope is not None:
            clauses.append("(r.scope='' OR r.scope=:scope)")
        if category is not None:
            clauses.append("r.category=:category")
        if terms:
            clauses.append("f.record_id IS NOT NULL")
        sql = (
            "SELECT r.id,r.category,r.scope,r.status,r.current_version,v.title,v.body,v.source_refs "
            "FROM memory_records r JOIN memory_versions v "
            "ON v.record_id=r.id AND v.version=r.current_version "
            + ("JOIN memory_fts f ON f.record_id=r.id AND memory_fts MATCH :expression " if terms else "")
            + "WHERE "
            + " AND ".join(clauses)
            + " ORDER BY r.id LIMIT :limit OFFSET :cursor"
        )
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        text(sql),
                        {
                            "pid": project_id,
                            "scope": scope,
                            "category": category,
                            "expression": expression,
                            "limit": limit + 1,
                            "cursor": cursor,
                        },
                    )
                )
                .mappings()
                .all()
            )
        items = []
        for row in rows[:limit]:
            item = dict(row)
            item["snippet"] = str(item.pop("body"))[:280]
            item["source_refs"] = json.loads(item["source_refs"])
            items.append(item)
        return {"items": items, "next_cursor": cursor + limit if len(rows) > limit else None}

    async def memory_reindex(self, project_id: str) -> int:
        """Rebuild FTS only from live current versions; tombstones cannot reappear."""
        async with self.session_factory() as session, session.begin():
            await self._project_exists(session, project_id)
            await session.execute(
                text("DELETE FROM memory_fts WHERE record_id IN (SELECT id FROM memory_records WHERE project_id=:pid)"),
                {"pid": project_id},
            )
            rows = (
                (
                    await session.execute(
                        text(
                            "SELECT r.id,v.title,v.body FROM memory_records r JOIN memory_versions v "
                            "ON v.record_id=r.id AND v.version=r.current_version "
                            "WHERE r.project_id=:pid AND r.deleted_at IS NULL"
                        ),
                        {"pid": project_id},
                    )
                )
                .mappings()
                .all()
            )
            for row in rows:
                await self._index_fts(session, row["id"], row["title"], row["body"])
        return len(rows)

    async def context_build(
        self,
        *,
        project_id: str,
        task_id: str,
        query: str = "",
        budget_chars: int = 16000,
        checkout_ref: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if budget_chars < 1:
            raise MemoryError("CONTEXT_BUDGET_TOO_SMALL", "Character budget must be positive")
        task = await self.task_read(project_id, task_id)
        async with self.session_factory() as session:
            checkpoint_row = (
                await session.execute(
                    text(
                        "SELECT id FROM checkpoints WHERE task_id=:tid AND project_id=:pid "
                        "ORDER BY task_version DESC LIMIT 1"
                    ),
                    {"tid": task_id, "pid": project_id},
                )
            ).first()
            policy_rows = (
                (
                    await session.execute(
                        text(
                            "SELECT r.id,d.relative_path,d.content_hash,v.body,v.title,v.source_refs "
                            "FROM memory_records r JOIN source_documents d ON d.id=r.source_document_id "
                            "JOIN memory_versions v ON v.record_id=r.id AND v.version=r.current_version "
                            "WHERE r.project_id=:pid AND r.category='policies' AND r.status='active' "
                            "AND (r.scope='' OR r.scope=:scope) AND r.deleted_at IS NULL ORDER BY r.id"
                        ),
                        {"pid": project_id, "scope": task["scope"]},
                    )
                )
                .mappings()
                .all()
            )
        checkpoint = await self.checkpoint_read(project_id, checkpoint_row[0]) if checkpoint_row else None
        project = await self.project_read(project_id)
        root = Path(project["root"])
        package: dict[str, Any] = {
            "schema_version": 1,
            "task_state": {
                "task_id": task_id,
                "objective": task["objective"],
                "acceptance_criteria": task["acceptance_criteria"],
                "status": task["status"],
                "version": task["version"],
                "checkpoint": checkpoint,
            },
            "policy_refs": [],
            "selected_items": [],
            "source_refs": [],
            "warnings": [],
            "missing_required": [],
            "usage": {"budget": budget_chars, "count": 0, "count_method": "serialized_utf8_characters", "model": None},
        }
        if checkout_ref is not None and checkpoint and checkpoint["checkout_ref"] != checkout_ref:
            package["warnings"].append("Checkout differs from checkpoint; revalidate changed paths")
        for policy in policy_rows:
            path = (root / policy["relative_path"]).resolve()
            try:
                data = await asyncio.to_thread(path.read_bytes)
            except OSError:
                data = b""
            if not path.is_relative_to(root) or _hash(data) != policy["content_hash"]:
                package["warnings"].append(f"Source changed: {policy['relative_path']}")
                package["missing_required"].append(str(policy["id"]))
                continue
            package["policy_refs"].append(str(policy["id"]))
            package["selected_items"].append(
                {
                    "id": policy["id"],
                    "category": "policies",
                    "title": policy["title"],
                    "body": policy["body"],
                    "source_refs": json.loads(policy["source_refs"]),
                }
            )
            package["source_refs"].extend(json.loads(policy["source_refs"]))

        def measure() -> int:
            while True:
                length = len(encoded(package))
                if package["usage"]["count"] == length:
                    return length
                package["usage"]["count"] = length

        mandatory = measure()
        if mandatory > budget_chars:
            raise MemoryError("CONTEXT_BUDGET_TOO_SMALL", f"Required context needs {mandatory} characters")
        search = await self.memory_search(project_id=project_id, query=query, scope=str(task["scope"]), limit=100)
        source_freshness: dict[str, bool] = {}

        async def refs_fresh(refs: list[str], record_id: str) -> bool:
            for ref in refs:
                if ref not in source_freshness:
                    async with self.session_factory() as session:
                        source = (
                            (
                                await session.execute(
                                    text(
                                        "SELECT relative_path,content_hash FROM source_documents "
                                        "WHERE id=:id AND project_id=:pid"
                                    ),
                                    {"id": ref, "pid": project_id},
                                )
                            )
                            .mappings()
                            .first()
                        )
                    if source is None:
                        source_freshness[ref] = True
                    else:
                        path = (root / source["relative_path"]).resolve()
                        try:
                            data = await asyncio.to_thread(path.read_bytes)
                        except OSError:
                            data = b""
                        source_freshness[ref] = path.is_relative_to(root) and _hash(data) == source["content_hash"]
                if not source_freshness[ref]:
                    if len(package["warnings"]) < 10:
                        package["warnings"].append(f"Related source changed for memory {record_id}")
                    return False
            return True

        for hit in cast(list[dict[str, Any]], search["items"]):
            if hit["id"] in package["policy_refs"] or hit["category"] == "policies":
                continue
            if not await refs_fresh(hit["source_refs"], hit["id"]):
                continue
            item = {
                "id": hit["id"],
                "category": hit["category"],
                "title": hit["title"],
                "snippet": hit["snippet"],
                "source_refs": hit["source_refs"],
            }
            package["selected_items"].append(item)
            package["source_refs"].extend(hit["source_refs"])
            package["source_refs"] = list(dict.fromkeys(package["source_refs"]))
            if measure() > budget_chars:
                package["selected_items"].pop()
                package["source_refs"] = list(
                    dict.fromkeys(ref for entry in package["selected_items"] for ref in entry["source_refs"])
                )

        # Expand one explicit edge from selected records, with a bounded count and the same scope/freshness gates.
        selected_ids = [str(item["id"]) for item in package["selected_items"]]
        related_count = 0
        for source_id in selected_ids:
            if related_count >= 10:
                break
            async with self.session_factory() as session:
                rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT rel.target_id,rel.relation_type,r.category,v.title,v.body,v.source_refs "
                                "FROM relations rel JOIN memory_records r ON r.id=rel.target_id "
                                "JOIN memory_versions v ON v.record_id=r.id AND v.version=r.current_version "
                                "WHERE rel.project_id=:pid AND rel.source_id=:source AND r.project_id=:pid "
                                "AND r.status='active' AND r.deleted_at IS NULL "
                                "AND (r.scope='' OR r.scope=:scope) ORDER BY rel.id LIMIT 10"
                            ),
                            {"pid": project_id, "source": source_id, "scope": task["scope"]},
                        )
                    )
                    .mappings()
                    .all()
                )
            for row in rows:
                target_id = str(row["target_id"])
                if target_id in {str(item["id"]) for item in package["selected_items"]}:
                    continue
                refs = cast(list[str], json.loads(row["source_refs"]))
                if not await refs_fresh(refs, target_id):
                    continue
                package["selected_items"].append(
                    {
                        "id": target_id,
                        "category": row["category"],
                        "title": row["title"],
                        "snippet": str(row["body"])[:280],
                        "source_refs": refs,
                        "related_from": source_id,
                        "relation_type": row["relation_type"],
                    }
                )
                package["source_refs"] = list(dict.fromkeys([*package["source_refs"], *refs]))
                if measure() > budget_chars:
                    package["selected_items"].pop()
                    package["source_refs"] = list(
                        dict.fromkeys(ref for entry in package["selected_items"] for ref in entry["source_refs"])
                    )
                    continue
                related_count += 1
                if related_count >= 10:
                    break
        while measure() > budget_chars:
            optional = next(
                (
                    index
                    for index in range(len(package["selected_items"]) - 1, -1, -1)
                    if package["selected_items"][index]["category"] != "policies"
                ),
                None,
            )
            if optional is None:
                raise MemoryError("CONTEXT_BUDGET_TOO_SMALL", f"Required context needs {measure()} characters")
            package["selected_items"].pop(optional)
            package["source_refs"] = list(
                dict.fromkeys(ref for entry in package["selected_items"] for ref in entry["source_refs"])
            )
        return package
