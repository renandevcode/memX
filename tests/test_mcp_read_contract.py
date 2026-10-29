import pytest
from mcp import Client

from project_memory.config import Settings
from project_memory.infrastructure.db import migrate
from project_memory.interfaces.mcp import create_mcp


@pytest.mark.asyncio
async def test_read_contract_exposes_record_id_and_reports_wrong_parameter(tmp_path):
    settings = Settings(data_dir=tmp_path / "data")
    migrate(settings.db_url)
    async with Client(create_mcp(settings)) as client:
        listing = await client.list_tools()
        tool = next(tool for tool in listing.tools if tool.name == "memory_read")
        assert "record_id" in tool.description
        invalid = await client.call_tool("memory_read", {"arguments": {"project_id": "p", "id": "r"}})
        assert invalid.is_error
        assert "record_id" in str(invalid.content)
        assert "INVALID_INPUT" in str(invalid.content)
