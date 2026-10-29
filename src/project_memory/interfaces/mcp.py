"""Official MCP SDK stdio adapter using the application service."""

from __future__ import annotations

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
                    result: dict[str, Any] = await method(**arguments)
                    return result
                except MemoryError as exc:
                    raise ToolError(f"{exc.code}: {exc.detail}") from exc
                finally:
                    await engine.dispose()

            return handler

        server.tool(name=operation)(make_handler(operation))
    return server


def main() -> None:
    config = Settings()
    migrate(config.db_url)
    create_mcp(config).run(transport="stdio")


if __name__ == "__main__":
    main()
