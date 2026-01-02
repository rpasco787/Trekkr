from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import is_sqlite_session


def test_is_sqlite_session_true_for_engine_bound_session():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        assert is_sqlite_session(session) is True
    finally:
        session.close()
        # Ensure underlying DBAPI connections are closed (important on py3.13+/py3.14,
        # where unclosed sqlite3 connections can surface as PytestUnraisableExceptionWarning)
        engine.dispose()


def test_is_sqlite_session_true_for_connection_bound_session():
    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    try:
        # Regression: `Connection` does not have `.url`
        assert is_sqlite_session(session) is True
    finally:
        session.close()
        connection.close()
        engine.dispose()


def test_is_sqlite_session_false_for_postgres_url():
    # Should not require a live database connection.
    engine = create_engine("postgresql+psycopg2://user:pass@localhost:5432/dbname")
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        assert is_sqlite_session(session) is False
    finally:
        session.close()
        engine.dispose()

