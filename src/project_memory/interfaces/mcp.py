"""Official MCP SDK stdio adapter using the application service."""

from __future__ import annotations

import inspect
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from project_memory.application.handoff import MemoryService
from project_memory.application.service import MemoryError
from project_memory.config import Settings
from project_memory.infrastructure.db import make_engine, migrate
from project_memory.interfaces.http import OPERATIONS


def create_mcp(settings: Settings | None = None) -> MCPServer:
    config = settings or Settings()
    server = MCPServer("MemX")

    for operation in sorted(OPERATIONS):

        def make_handler(name: str) -> Any:
            async def handler(arguments: dict[str, Any]) -> dict[str, Any]:
                """Invoke a MemX operation with its named arguments as a JSON object."""
                engine = make_engine(config.db_url)
                try:
                    method = getattr(MemoryService(engine), name)
                    try:
                        inspect.signature(method).bind(**arguments)
                    except TypeError as exc:
                        raise ToolError(f"INVALID_INPUT: {exc}") from exc
                    result: Any = await method(**arguments)
                    if isinstance(result, dict):
                        return result
                    return {"items": result} if isinstance(result, list) else {"result": result}
                except MemoryError as exc:
                    raise ToolError(f"{exc.code}: {exc.detail}") from exc
                finally:
                    await engine.dispose()

            return handler

        signature = inspect.signature(getattr(MemoryService, operation))
        parameters = [str(parameter) for key, parameter in signature.parameters.items() if key != "self"]
        description = f"{operation}: pass these named parameters inside arguments: " + ", ".join(parameters)
        server.tool(name=operation, description=description)(make_handler(operation))
    return server


def main() -> None:
    config = Settings()
    migrate(config.db_url)
    create_mcp(config).run(transport="stdio")


if __name__ == "__main__":
    main()
