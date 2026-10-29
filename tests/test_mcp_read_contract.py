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
        assert "extra_forbidden" in str(invalid.content)
        schema = tool.input_schema
        assert "record_id" in str(schema)
        assert "additionalProperties" in str(schema)


def test_contract_rejects_test_hooks_unknown_fields_and_wrong_types():
    from pydantic import ValidationError

    from project_memory.interfaces.contracts import CONTRACTS, validate_arguments

    assert "fail_after_update" not in CONTRACTS["task_checkpoint"].model_fields
    with pytest.raises(ValidationError):
        validate_arguments("memory_read", {"project_id": "p", "record_id": "r", "version": "1"})
    with pytest.raises(ValidationError):
        validate_arguments("memory_read", {"project_id": "p", "record_id": "r", "memory_id": "r"})
    assert validate_arguments("memory_read", {"project_id": "p", "record_id": "r"})["version"] is None
