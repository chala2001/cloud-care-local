import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ["DATABASE_URL"]
DB_SCHEMA    = os.environ.get("DB_SCHEMA", "patients")

# connect_args is only needed for SQLite (used in tests)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def set_search_path(dbapi_conn, connection_record):
    """
    Set the PostgreSQL search_path to our service's schema on every new connection.
    This means every query automatically targets the 'patients' schema without
    needing to prefix table names.
    SQLite does not support schemas, so we skip this for test connections.
    """
    if DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_conn.cursor()
    cursor.execute(f"SET search_path TO {DB_SCHEMA}")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a database session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables defined by SQLAlchemy models. Called at startup."""
    Base.metadata.create_all(bind=engine)