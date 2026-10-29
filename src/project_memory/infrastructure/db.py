"""Async SQLite engine and migration entry point."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(db_url: str) -> AsyncEngine:
    engine = create_async_engine(db_url, connect_args={"timeout": 5})

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_options(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def migrate(db_url: str) -> None:
    if not db_url.startswith("sqlite+aiosqlite:///"):
        raise ValueError("MVP migrations require a local SQLite URL")
    db_path = Path(db_url.removeprefix("sqlite+aiosqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
