from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from alembic import context
from app import models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base

config = context.config
# ConfigParser treats percent-encoded password characters as interpolation.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Integration tests can run the real history inside a restricted-role outer
    # transaction. Normal CLI deployments still create their own connection.
    supplied = config.attributes.get("connection")
    if supplied is not None:
        if not isinstance(supplied, Connection):
            raise TypeError("Expected a SQLAlchemy migration connection")
        migrate_connection(supplied)
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        migrate_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
