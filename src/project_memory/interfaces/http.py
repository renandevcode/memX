"""Token-protected loopback HTTP adapter for the common service."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from project_memory.application.handoff import MemoryService
from project_memory.application.service import MemoryError
from project_memory.application.storage import Store
from project_memory.config import Settings
from project_memory.infrastructure.db import make_engine
from project_memory.interfaces.contracts import (
    OPERATIONS,
    OUTPUT_TYPES,
    operation_model,
    validate_arguments,
    validate_output,
)
from project_memory.observability import operation_span


def create_app(settings: Settings | None = None, engine: Store | None = None) -> FastAPI:
    config = settings or Settings()
    if not config.http_token:
        raise ValueError("MEMX_HTTP_TOKEN is required for HTTP")
    own_engine = engine is None
    db_engine = engine or make_engine(config.db_url)
    service = MemoryService(db_engine, config.excluded_paths)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if own_engine:
                await db_engine.dispose()

    app = FastAPI(title="MemX local API", version="1", lifespan=lifespan)

    async def invoke(operation: str, request: Any, authorization: str | None) -> Any:
        expected = f"Bearer {config.http_token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail={"code": "ACCESS_DENIED"})
        try:
            arguments = validate_arguments(operation, request.arguments.model_dump())
        except (TypeError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_INPUT"}) from exc
        try:
            with operation_span(operation, arguments.get("project_id")):
                result = await getattr(service, operation)(**arguments)
                validated = validate_output(operation, result)
        except MemoryError as exc:
            status = 409 if exc.code.endswith("CONFLICT") else 400
            if exc.code == "NOT_FOUND":
                status = 404
            raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.detail}) from exc
        return validated.model_dump() if isinstance(validated, BaseModel) else validated

    for name in sorted(OPERATIONS):
        request_model = create_model(
            name + "Request",
            __config__=ConfigDict(extra="forbid"),
            schema_version=(Literal[1], 1),
            arguments=(operation_model(name), ...),
        )

        def make_endpoint(operation: str, model: type[BaseModel]) -> Any:
            async def endpoint(request: BaseModel, authorization: str | None = Header(default=None)) -> Any:
                return await invoke(operation, request, authorization)

            endpoint.__annotations__["request"] = model
            return endpoint

        app.add_api_route(
            f"/v1/{name}",
            make_endpoint(name, request_model),
            methods=["POST"],
            response_model=OUTPUT_TYPES[name],
            name=name,
        )

    return app
