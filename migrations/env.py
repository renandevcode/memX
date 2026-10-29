"""Alembic migration environment."""

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config


if context.is_offline_mode():
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    url = config.get_main_option("sqlalchemy.url").replace("sqlite+aiosqlite:", "sqlite:")
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
