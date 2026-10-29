import pytest

from project_memory.config import Settings
from project_memory.infrastructure.db import migrate
from project_memory.interfaces.activation import activate


@pytest.mark.asyncio
async def test_activation_preserves_instructions_and_is_repeatable(tmp_path):
    root = tmp_path / "game"
    root.mkdir()
    (root / "AGENTS.md").write_text("Existing instructions\n")
    settings = Settings(data_dir=tmp_path / "external")
    migrate(settings.db_url)
    first = await activate(root, settings)
    contents = (root / "AGENTS.md").read_text()
    assert contents.startswith("Existing instructions\n")
    assert first["project_id"] in contents
    assert await activate(root, settings) == first
    assert (root / "AGENTS.md").read_text() == contents
    assert "project_memory.interfaces.mcp" in (root / ".codex/config.toml").read_text()
