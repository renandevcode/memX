"""Official MCP SDK stdio adapter using the application service."""

from __future__ import annotations

import inspect
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from project_memory.application.handoff import MemoryService
from project_memory.application.service import MemoryError
from project_memory.config import Settings
from project_memory.infrastructure.db import make_engine, migrate
from project_memory.interfaces.binding import resolve_binding
from project_memory.interfaces.contracts import OPERATIONS, operation_model, validate_output


def create_mcp(settings: Settings | None = None) -> MCPServer:
    config, binding = (settings, None) if settings is not None else resolve_binding()
    server = MCPServer("MemX")

    for operation in sorted(OPERATIONS):

        def make_handler(name: str) -> Any:
            async def handler(arguments: BaseModel) -> dict[str, Any]:
                """Invoke a MemX operation with its named arguments as a JSON object."""
                engine = make_engine(config.db_url)
                try:
                    service = MemoryService(engine)
                    if binding:
                        arguments_dict = arguments.model_dump()
                        if arguments_dict.get("project_id", binding.project_id) != binding.project_id:
                            raise MemoryError("ACCESS_DENIED", "Project differs from current activation")
                        project = await service.project_read(binding.project_id)
                        if project["root"] != binding.root:
                            raise MemoryError("ACCESS_DENIED", "Database root differs from activation")
                    method = getattr(service, name)
                    try:
                        inspect.signature(method).bind(**arguments.model_dump())
                    except TypeError as exc:
                        raise ToolError(f"INVALID_INPUT: {exc}") from exc
                    result: Any = validate_output(name, await method(**arguments.model_dump()))
                    if isinstance(result, BaseModel):
                        result = result.model_dump()
                    elif isinstance(result, list):
                        result = [item.model_dump() if isinstance(item, BaseModel) else item for item in result]
                    if isinstance(result, dict):
                        return result
                    return {"items": result} if isinstance(result, list) else {"result": result}
                except MemoryError as exc:
                    raise ToolError(f"{exc.code}: {exc.detail}") from exc
                finally:
                    await engine.dispose()

            handler.__annotations__["arguments"] = operation_model(name, binding.project_id if binding else None)
            return handler

        signature = inspect.signature(getattr(MemoryService, operation))
        parameters = [
            str(parameter)
            for key, parameter in signature.parameters.items()
            if key not in {"self", "fail_after_update"}
        ]
        description = f"{operation}: pass these named parameters inside arguments: " + ", ".join(parameters)
        server.tool(name=operation, description=description)(make_handler(operation))
    return server


def main() -> None:
    config, _binding = resolve_binding()
    migrate(config.db_url)
    create_mcp().run(transport="stdio")


if __name__ == "__main__":
    main()
