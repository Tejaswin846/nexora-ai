from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Connection, Engine
except Exception:  # pragma: no cover - optional at import time for minimal installs
    create_engine = None
    text = None
    Connection = Any  # type: ignore
    Engine = Any  # type: ignore

try:
    from config import Settings, get_settings
except Exception:
    from .config import Settings, get_settings


LOCAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS software_reliability_decisions (
    decision_id TEXT PRIMARY KEY,
    audit_event_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    environment TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    selected_decision TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    validator_version TEXT NOT NULL,
    reliability_engine_version TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_software_reliability_decisions_tenant
ON software_reliability_decisions (organization_id, project_id, environment, workflow_id, trace_id, step_id);

CREATE TABLE IF NOT EXISTS software_audit_events (
    audit_event_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    environment TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    selected_decision TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_software_audit_events_tenant
ON software_audit_events (organization_id, project_id, environment, workflow_id, trace_id, step_id);
"""


@dataclass
class DatabaseSession:
    backend: str
    connection: Any
    closed: bool = False

    def execute(self, query: Any, params: Optional[dict[str, Any] | tuple[Any, ...]] = None) -> Any:
        if self.closed:
            raise RuntimeError("Database session is closed.")
        if self.backend == "sqlite":
            return self.connection.execute(query, params or ())
        if text is not None and isinstance(query, str):
            query = text(query)
        return self.connection.execute(query, params or {})

    def commit(self) -> None:
        if self.closed:
            return
        if self.backend == "sqlite":
            self.connection.commit()
        elif hasattr(self.connection, "commit"):
            self.connection.commit()

    def close(self) -> None:
        if self.closed:
            return
        self.connection.close()
        self.closed = True


_engine: Engine | None = None


def normalize_database_url(settings: Settings) -> str:
    url = (settings.database_url or "").strip()
    if url:
        return url
    return f"sqlite:///{Path(settings.data_dir).expanduser() / 'nexora_dev.sqlite3'}"


def is_sqlite_url(database_url: str) -> bool:
    clean = database_url.strip().lower()
    return clean.startswith("sqlite:") or clean.endswith(".sqlite") or clean.endswith(".sqlite3")


def validate_database_settings(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    database_url = normalize_database_url(settings)
    if settings.is_production_like:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL is required in production/staging.")
        if is_sqlite_url(database_url):
            raise RuntimeError("SQLite database URLs are only allowed in development or test.")
    return database_url


def sqlite_path_from_url(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///"):]).expanduser()
    if database_url.startswith("sqlite://"):
        return Path(database_url[len("sqlite://"):]).expanduser()
    return Path(database_url).expanduser()


def init_database(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    database_url = validate_database_settings(settings)
    if is_sqlite_url(database_url):
        path = sqlite_path_from_url(database_url)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        try:
            connection.executescript(LOCAL_SCHEMA)
            connection.commit()
        finally:
            connection.close()


def open_database_session(settings: Settings | None = None) -> DatabaseSession:
    global _engine
    settings = settings or get_settings()
    database_url = validate_database_settings(settings)
    if is_sqlite_url(database_url):
        path = sqlite_path_from_url(database_url)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return DatabaseSession("sqlite", connection)

    if create_engine is None:
        raise RuntimeError("SQLAlchemy is required for production database connections.")
    if _engine is None:
        _engine = create_engine(database_url, pool_pre_ping=True)
    return DatabaseSession("sqlalchemy", _engine.connect())


def session_scope(settings: Settings | None = None) -> Iterator[DatabaseSession]:
    session = open_database_session(settings)
    try:
        yield session
    finally:
        session.close()
