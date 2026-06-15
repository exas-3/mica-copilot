"""Write-only conversation log.

Persists each user question + the agent's answer to the ``chat_logs`` table for quality
monitoring and debugging.

IMPORTANT — this log is intentionally **not accessible to the agent**: no tool
(``search_regulation`` / ``search_news`` / ``lookup_register`` / ``check_enforcement``), no
retrieval path (``app.services.rag``), and no context builder reads from ``chat_logs``. This
module only ever *writes*. So the assistant can never surface another user's conversation.

Logging is best-effort: any failure here is swallowed so it can never break a chat response.
"""
from __future__ import annotations

from psycopg.types.json import Jsonb

from app.db import get_conn

_ensured = False

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chat_logs (
    id          bigserial   PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now(),
    question    text        NOT NULL,
    answer      text        NOT NULL DEFAULT '',
    grounded    boolean     NOT NULL DEFAULT false,
    model       text,
    citations   jsonb       NOT NULL DEFAULT '[]'::jsonb,
    tool_events jsonb       NOT NULL DEFAULT '[]'::jsonb,
    usage       jsonb       NOT NULL DEFAULT '{}'::jsonb
)
"""
_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS chat_logs_created_idx ON chat_logs (created_at DESC)"

_INSERT = """
INSERT INTO chat_logs (question, answer, grounded, model, citations, tool_events, usage)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""


def ensure_table() -> None:
    """Create the table once (idempotent). Safe to call on startup or before the first write."""
    global _ensured
    if _ensured:
        return
    try:
        with get_conn() as conn:
            conn.execute(_CREATE_TABLE)
            conn.execute(_CREATE_INDEX)
        _ensured = True
    except Exception:  # noqa: BLE001 — never block startup/chat on logging
        pass


def log_turn(
    question: str,
    answer: str,
    *,
    grounded: bool = False,
    model: str | None = None,
    citations: list | None = None,
    tool_events: list | None = None,
    usage: dict | None = None,
) -> None:
    """Append one completed turn. Never raises."""
    try:
        ensure_table()
        with get_conn() as conn:
            conn.execute(
                _INSERT,
                (
                    question,
                    answer or "",
                    bool(grounded),
                    model,
                    Jsonb(citations or []),
                    Jsonb(tool_events or []),
                    Jsonb(usage or {}),
                ),
            )
    except Exception:  # noqa: BLE001 — logging must never break the chat
        pass
