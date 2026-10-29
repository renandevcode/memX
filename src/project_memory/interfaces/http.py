"""Token-protected loopback HTTP adapter for the common service."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from project_memory.application.handoff import MemoryService
from project_memory.application.service import MemoryError
from project_memory.config import Settings
from project_memory.infrastructure.db import make_engine
from project_memory.interfaces.contracts import OPERATIONS, validate_arguments, validate_output


class OperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    arguments: dict[str, Any]


def create_app(settings: Settings | None = None, engine: AsyncEngine | None = None) -> FastAPI:
    config = settings or Settings()
    if not config.http_token:
        raise ValueError("MEMX_HTTP_TOKEN is required for HTTP")
    own_engine = engine is None
    db_engine = engine or make_engine(config.db_url)
    service = MemoryService(db_engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if own_engine:
                await db_engine.dispose()

    app = FastAPI(title="MemX local API", version="1", lifespan=lifespan)

    @app.post("/v1/{operation}")
    async def invoke(
        operation: str, request: OperationRequest, authorization: str | None = Header(default=None)
    ) -> Any:
        expected = f"Bearer {config.http_token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail={"code": "ACCESS_DENIED"})
        if operation not in OPERATIONS:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        try:
            arguments = validate_arguments(operation, request.arguments)
        except (TypeError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_INPUT"}) from exc
        try:
            result = await getattr(service, operation)(**arguments)
        except MemoryError as exc:
            status = 409 if exc.code.endswith("CONFLICT") else 400
            if exc.code == "NOT_FOUND":
                status = 404
            raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.detail}) from exc
        validated = validate_output(operation, result)
        return validated.model_dump() if isinstance(validated, BaseModel) else validated

    return app
