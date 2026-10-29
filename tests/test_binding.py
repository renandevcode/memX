import json

import pytest

from project_memory.interfaces.binding import resolve_binding
from project_memory.interfaces.contracts import operation_model


def test_binding_resolves_parent_and_rejects_wrong_database(tmp_path, monkeypatch):
    monkeypatch.delenv("MEMX_DATA_DIR", raising=False)
    root = tmp_path / "project"
    nested = root / "src"
    nested.mkdir(parents=True)
    data = tmp_path / "data"
    (root / ".memx.json").write_text(json.dumps({"root": str(root), "project_id": "project-a", "data_dir": str(data)}))
    settings, binding = resolve_binding(nested)
    assert settings.data_dir == data
    assert binding.project_id == "project-a"
    model = operation_model("memory_search", binding.project_id)
    assert model.model_validate({"query": "game"}).model_dump()["project_id"] == "project-a"
    monkeypatch.setenv("MEMX_DATA_DIR", str(tmp_path / "wrong"))
    with pytest.raises(ValueError, match="conflicts"):
        resolve_binding(nested)
