import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage


@contextmanager
def _get_conn():
    path = os.environ.get("DB_PATH", "conversations.db")
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                phone TEXT PRIMARY KEY,
                messages TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                phone TEXT PRIMARY KEY,
                name TEXT,
                business_type TEXT,
                size TEXT,
                pain_point TEXT,
                is_hot INTEGER DEFAULT 0,
                juan_notified INTEGER DEFAULT 0,
                hot_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def _serialize(messages: list[BaseMessage]) -> str:
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "ai", "content": msg.content})
    return json.dumps(result)


def _deserialize(data: str) -> list[BaseMessage]:
    result = []
    for item in json.loads(data):
        if item["role"] == "human":
            result.append(HumanMessage(content=item["content"]))
        elif item["role"] == "ai":
            result.append(AIMessage(content=item["content"]))
    return result


def load_messages(phone: str) -> list[BaseMessage]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT messages FROM conversations WHERE phone = ?", (phone,)
        ).fetchone()
    if row is None:
        return []
    return _deserialize(row["messages"])


def save_messages(phone: str, messages: list[BaseMessage]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO conversations (phone, messages, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                messages = excluded.messages,
                updated_at = excluded.updated_at
        """, (phone, _serialize(messages), now))


def load_lead(phone: str) -> dict:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT name, business_type, size, pain_point, is_hot FROM leads WHERE phone = ?",
            (phone,)
        ).fetchone()
    if row is None:
        return {}
    return {k: row[k] for k in ("name", "business_type", "size", "pain_point", "is_hot") if row[k] is not None}


def save_lead(phone: str, lead_data: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    is_hot = int(bool(lead_data.get("is_hot", False)))
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO leads (phone, name, business_type, size, pain_point, is_hot, hot_reason, juan_notified, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                name = COALESCE(excluded.name, leads.name),
                business_type = COALESCE(excluded.business_type, leads.business_type),
                size = COALESCE(excluded.size, leads.size),
                pain_point = COALESCE(excluded.pain_point, leads.pain_point),
                is_hot = MAX(excluded.is_hot, leads.is_hot),
                hot_reason = COALESCE(excluded.hot_reason, leads.hot_reason),
                updated_at = excluded.updated_at
        """, (
            phone,
            lead_data.get("name"),
            lead_data.get("business_type"),
            lead_data.get("size"),
            lead_data.get("pain_point"),
            is_hot,
            lead_data.get("hot_reason"),
            now,
            now,
        ))


def is_juan_notified(phone: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT juan_notified FROM leads WHERE phone = ?", (phone,)
        ).fetchone()
    if row is None:
        return False
    return bool(row["juan_notified"])


def mark_juan_notified(phone: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO leads (phone, juan_notified, is_hot, created_at, updated_at)
            VALUES (?, 1, 0, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                juan_notified = 1,
                updated_at = excluded.updated_at
        """, (phone, now, now))
