"""Async SQLite engine and migration entry point."""

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from project_memory.application.storage import Session


class SqliteSession:
    def __init__(self, inner: AsyncSession):
        self.inner = inner

    async def __aenter__(self) -> Session:
        await self.inner.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.inner.__aexit__(exc_type, exc, tb)

    def begin(self) -> Any:
        return self.inner.begin()

    async def execute(self, query: str, params: Any = None) -> Any:
        return await self.inner.execute(text(query), params)


class SqliteStore:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    def session_factory(self) -> Session:
        return SqliteSession(self._sessions())

    async def dispose(self) -> None:
        await self.engine.dispose()


def make_engine(db_url: str) -> SqliteStore:
    engine = create_async_engine(db_url, connect_args={"timeout": 5})

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_options(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return SqliteStore(engine)


def migrate(db_url: str) -> None:
    if not db_url.startswith("sqlite+aiosqlite:///"):
        raise ValueError("MVP migrations require a local SQLite URL")
    db_path = Path(db_url.removeprefix("sqlite+aiosqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
