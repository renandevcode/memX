"""Resolve explicit project activation from the current directory or its parents."""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from project_memory.config import Settings


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    project_id: str
    root: str
    data_dir: str


def resolve_binding(start: Path | None = None) -> tuple[Settings, Binding | None]:
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        marker = directory / ".memx.json"
        if not marker.exists():
            continue
        if marker.is_symlink():
            raise ValueError("Project marker must not be a symlink")
        binding = Binding.model_validate_json(marker.read_text())
        if Path(binding.root).resolve() != directory:
            raise ValueError("Project marker belongs to another root")
        configured = os.environ.get("MEMX_DATA_DIR")
        if configured and Path(configured).resolve() != Path(binding.data_dir).resolve():
            raise ValueError("MEMX_DATA_DIR conflicts with this project's activation")
        return Settings(data_dir=Path(binding.data_dir)), binding
    return Settings(), None
