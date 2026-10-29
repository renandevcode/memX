import pytest
from mcp import Client

from project_memory.config import Settings
from project_memory.infrastructure.db import migrate
from project_memory.interfaces.http import create_app
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


def test_output_contracts_cover_operations_and_reject_invalid_results():
    from pydantic import ValidationError

    from project_memory.interfaces.contracts import OPERATIONS, OUTPUT_ADAPTERS, validate_output

    assert OUTPUT_ADAPTERS.keys() == OPERATIONS
    assert validate_output("memory_reindex", 2) == 2
    assert validate_output("source_index", []) == []
    with pytest.raises(ValidationError):
        validate_output("memory_reindex", "2")
    with pytest.raises(ValidationError):
        validate_output("memory_search", {"items": [], "next_cursor": "1"})
    with pytest.raises(ValidationError):
        validate_output("session_end", {"id": "s", "status": "ended", "unexpected": True})


def test_openapi_exposes_operation_specific_inputs_and_outputs(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, http_token="test-token"))
    spec = app.openapi()
    operation = spec["paths"]["/v1/memory_read"]["post"]
    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert request_ref.endswith("/memory_readRequest")
    assert response_ref.endswith("/MemoryRead")
    arguments_ref = spec["components"]["schemas"]["memory_readRequest"]["properties"]["arguments"]["$ref"]
    assert "record_id" in spec["components"]["schemas"][arguments_ref.rsplit("/", 1)[-1]]["properties"]
