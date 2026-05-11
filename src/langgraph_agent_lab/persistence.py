"""Checkpointer adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> Any | None:
    """Return a LangGraph checkpointer.

    Supported kinds:
    - ``"none"`` — no persistence (stateless runs).
    - ``"memory"`` — in-process MemorySaver (default, no extra deps).
    - ``"sqlite"`` — SQLite with WAL mode for crash-resume evidence.
    - ``"postgres"`` — PostgreSQL (requires langgraph-checkpoint-postgres).
    """
    if kind == "none":
        return None

    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    if kind == "sqlite":
        import sqlite3

        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise RuntimeError(
                "SQLite checkpointer requires: pip install langgraph-checkpoint-sqlite"
            ) from exc

        db_path = database_url or "outputs/checkpoints.db"
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return SqliteSaver(conn=conn)

    if kind == "postgres":
        try:
            from langgraph.checkpoint.postgres import (
                PostgresSaver,  # type: ignore[import-not-found]
            )
        except ImportError as exc:
            raise RuntimeError(
                "Postgres checkpointer requires: pip install langgraph-checkpoint-postgres"
            ) from exc
        return PostgresSaver.from_conn_string(database_url or "")

    raise ValueError(f"Unknown checkpointer kind: {kind!r}. Choose: none, memory, sqlite, postgres")
