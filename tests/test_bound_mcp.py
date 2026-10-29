import json
import sys
import tomllib

import pytest
from mcp import Client, StdioServerParameters

from project_memory.config import Settings
from project_memory.infrastructure.db import migrate
from project_memory.interfaces.activation import activate


@pytest.mark.asyncio
async def test_bound_stdio_defaults_project_and_rejects_cross_project(tmp_path):
    root = tmp_path / "game"
    root.mkdir()
    settings = Settings(data_dir=tmp_path / "data")
    migrate(settings.db_url)
    binding = await activate(root, settings)
    config = tomllib.loads((root / ".codex/config.toml").read_text())["mcp_servers"]["memx"]
    assert config["cwd"] == str(root)
    params = StdioServerParameters(command=sys.executable, args=config["args"], cwd=config["cwd"], env=config["env"])
    async with Client(params) as client:
        created = await client.call_tool(
            "memory_create",
            {"arguments": {"category": "decisions", "title": "Lives", "body": "Three lives", "status": "active"}},
        )
        assert not created.is_error
        rid = created.structured_content["id"]
        read = await client.call_tool("memory_read", {"arguments": {"record_id": rid}})
        assert read.structured_content["project_id"] == binding["project_id"]
        denied = await client.call_tool(
            "memory_read", {"arguments": {"record_id": rid, "project_id": "another-project"}}
        )
        assert denied.is_error
        assert "ACCESS_DENIED" in str(denied.content)
    # Verify persisted retrieval through a newly launched bound server process.
    async with Client(params) as second:
        result = await second.call_tool("memory_search", {"arguments": {"query": "Lives"}})
        assert rid in json.dumps(result.structured_content)
