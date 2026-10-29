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


@pytest.mark.asyncio
async def test_activation_recovers_interrupted_write(tmp_path, monkeypatch):
    from project_memory.interfaces import activation

    root = tmp_path / "game"
    root.mkdir()
    settings = Settings(data_dir=tmp_path / "external")
    migrate(settings.db_url)
    original = activation.atomic_write

    def fail_on_instructions(path, content):
        if path.name == "AGENTS.md":
            raise OSError("injected failure")
        original(path, content)

    monkeypatch.setattr(activation, "atomic_write", fail_on_instructions)
    with pytest.raises(OSError, match="injected"):
        await activate(root, settings)
    assert not (root / ".memx.json").exists()
    monkeypatch.setattr(activation, "atomic_write", original)
    await activate(root, settings)
    assert (root / ".codex/config.toml").read_text().count("[mcp_servers.memx]") == 1
    assert (root / "AGENTS.md").read_text().count("<!-- memx:start -->") == 1


@pytest.mark.asyncio
async def test_activation_rejects_symlink_before_reading_marker(tmp_path):
    root = tmp_path / "game"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("private")
    (root / ".memx.json").symlink_to(outside)
    with pytest.raises(ValueError, match="inside"):
        await activate(root, Settings(data_dir=tmp_path / "data"))
    assert outside.read_text() == "private"
