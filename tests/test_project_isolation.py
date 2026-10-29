"""Verify that separate project-bound MCP processes cannot cross project data."""

import sys

import pytest
from mcp import Client, StdioServerParameters

from project_memory.config import Settings
from project_memory.infrastructure.db import migrate
from project_memory.interfaces.activation import activate


async def call(client, operation, **arguments):
    result = await client.call_tool(operation, {"arguments": arguments})
    assert not result.is_error, result.content
    assert result.structured_content is not None
    return result.structured_content.get("result", result.structured_content)


@pytest.mark.asyncio
async def test_two_activated_projects_are_isolated_over_stdio(tmp_path):
    data_dir = tmp_path / "data"
    settings = Settings(data_dir=data_dir)
    migrate(settings.db_url)
    roots = [tmp_path / "project-a", tmp_path / "project-b"]
    for root in roots:
        root.mkdir()
    project_a, project_b = [await activate(root, settings) for root in roots]
    assert project_a["project_id"] != project_b["project_id"]

    def params(root):
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "project_memory.interfaces.mcp"],
            cwd=root,
            env={"MEMX_DATA_DIR": str(data_dir)},
        )

    async with Client(params(roots[0])) as client_a, Client(params(roots[1])) as client_b:
        record_a = await call(
            client_a,
            "memory_create",
            category="decisions",
            title="Project A marker",
            body="Only project A uses amber widgets.",
            status="active",
        )
        record_b = await call(
            client_b,
            "memory_create",
            category="decisions",
            title="Project B marker",
            body="Only project B uses violet widgets.",
            status="active",
        )

        search_a = await call(client_a, "memory_search", query="widgets")
        search_b = await call(client_b, "memory_search", query="widgets")
        assert [item["id"] for item in search_a["items"]] == [record_a["id"]]
        assert [item["id"] for item in search_b["items"]] == [record_b["id"]]

        cross_read = await client_b.call_tool("memory_read", {"arguments": {"record_id": record_a["id"]}})
        assert cross_read.is_error
        assert "INVALID_REFERENCE" in str(cross_read.content) or "NOT_FOUND" in str(cross_read.content)

        wrong_project = await client_b.call_tool(
            "memory_search", {"arguments": {"project_id": project_a["project_id"], "query": "widgets"}}
        )
        assert wrong_project.is_error
