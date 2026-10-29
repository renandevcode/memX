"""Local runtime configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMX_", extra="ignore")

    data_dir: Path = Path.home() / ".local" / "share" / "memx"
    http_token: str | None = None
    http_host: str = "127.0.0.1"
    http_port: int = 8765

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.data_dir / 'memx.sqlite3'}"
