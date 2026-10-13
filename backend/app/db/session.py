from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


from sqlalchemy import text


def ensure_sqlite_column(engine_instance, table_name: str, column_name: str, column_type_sql: str) -> None:
    """Ensure a column exists on a table in SQLite; if missing, execute ALTER TABLE ADD COLUMN."""
    with engine_instance.connect() as conn:
        res = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        existing_cols = {row[1] for row in res}
        if existing_cols and column_name not in existing_cols:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_sql}"))
            conn.commit()


def run_sqlite_migrations(engine_instance=engine) -> None:
    """Run lightweight schema migrations for existing SQLite databases."""
    try:
        ensure_sqlite_column(engine_instance, "courses", "kb_error", "TEXT")
        ensure_sqlite_column(engine_instance, "courses", "kb_built_at", "DATETIME")
    except Exception:
        pass


if settings.database_url.startswith("sqlite"):
    run_sqlite_migrations(engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and handles closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

