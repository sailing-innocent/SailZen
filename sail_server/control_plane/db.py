from contextlib import contextmanager
from pathlib import Path
from typing import Generator
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker


ControlPlaneORMBase = declarative_base()


def _normalize_database_uri(uri: str) -> str:
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+psycopg://", 1)
    return uri


class ControlPlaneDatabase:
    _instance: "ControlPlaneDatabase | None" = None

    @classmethod
    def get_instance(cls) -> "ControlPlaneDatabase":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        uri = os.environ.get("CONTROL_PLANE_DATABASE_URI")
        if not uri:
            default_path = os.environ.get(
                "CONTROL_PLANE_SQLITE_PATH", "data/control_plane/control_plane.db"
            )
            Path(default_path).parent.mkdir(parents=True, exist_ok=True)
            uri = f"sqlite:///{default_path}"

        self.uri = _normalize_database_uri(uri)
        connect_args = (
            {"check_same_thread": False} if self.uri.startswith("sqlite") else {}
        )
        self.engine = create_engine(self.uri, connect_args=connect_args)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def create_all(self) -> None:
        ControlPlaneORMBase.metadata.create_all(bind=self.engine)
        self._ensure_schema_compatibility()

    def _ensure_schema_compatibility(self) -> None:
        inspector = inspect(self.engine)
        if not inspector.has_table("session_events"):
            return

        session_event_columns = {
            column["name"] for column in inspector.get_columns("session_events")
        }
        edge_node_columns = (
            {column["name"] for column in inspector.get_columns("edge_nodes")}
            if inspector.has_table("edge_nodes")
            else set()
        )
        session_action_columns = (
            {column["name"] for column in inspector.get_columns("session_actions")}
            if inspector.has_table("session_actions")
            else set()
        )
        workspace_columns = (
            {column["name"] for column in inspector.get_columns("remote_workspaces")}
            if inspector.has_table("remote_workspaces")
            else set()
        )
        session_columns = (
            {column["name"] for column in inspector.get_columns("opencode_sessions")}
            if inspector.has_table("opencode_sessions")
            else set()
        )

        statements: list[str] = []
        if "sequence_id" not in session_event_columns:
            statements.append(
                "ALTER TABLE session_events ADD COLUMN sequence_id INTEGER"
            )
        if "idempotency_key" not in session_event_columns:
            statements.append(
                "ALTER TABLE session_events ADD COLUMN idempotency_key VARCHAR(200)"
            )
        if "ack_cursor" not in edge_node_columns:
            statements.append(
                "ALTER TABLE edge_nodes ADD COLUMN ack_cursor INTEGER DEFAULT 0"
            )
        if "edge_ack_status" not in session_action_columns:
            statements.append(
                "ALTER TABLE session_actions ADD COLUMN edge_ack_status VARCHAR(50) DEFAULT 'pending'"
            )
        if "edge_ack_at" not in session_action_columns:
            statements.append(
                "ALTER TABLE session_actions ADD COLUMN edge_ack_at DATETIME"
            )
        if "inventory_source" not in workspace_columns:
            statements.append(
                "ALTER TABLE remote_workspaces ADD COLUMN inventory_source VARCHAR(50) DEFAULT 'edge-config'"
            )
        if "local_path" not in session_columns:
            statements.append(
                "ALTER TABLE opencode_sessions ADD COLUMN local_path VARCHAR(1000)"
            )
        if "diagnostics" not in session_columns:
            statements.append(
                "ALTER TABLE opencode_sessions ADD COLUMN diagnostics JSON"
            )

        if not statements:
            return

        with self.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

            if "sequence_id" not in session_event_columns:
                connection.execute(
                    text(
                        "UPDATE session_events SET sequence_id = id WHERE sequence_id IS NULL"
                    )
                )
            if "idempotency_key" not in session_event_columns:
                connection.execute(
                    text(
                        "UPDATE session_events SET idempotency_key = event_key WHERE idempotency_key IS NULL"
                    )
                )

    def get_db(self) -> Generator[Session, None, None]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_db_session(self) -> Session:
        return self.SessionLocal()


g_control_plane_db_func = ControlPlaneDatabase.get_instance().get_db


async def get_control_plane_db_dependency():
    return g_control_plane_db_func()


@contextmanager
def get_control_plane_db_session():
    db = ControlPlaneDatabase.get_instance().get_db_session()
    try:
        yield db
    finally:
        db.close()
