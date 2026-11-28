import json
from contextlib import contextmanager

import psycopg
from psycopg.types.json import Jsonb

from ticket_assistant.config import DATABASE_URL


def jsonb(value):
    return Jsonb(value, dumps=lambda v: json.dumps(v, ensure_ascii=False, default=str))


@contextmanager
def connect():
    with psycopg.connect(DATABASE_URL, autocommit=True, connect_timeout=10) as conn:
        yield conn


class History:
    def new_session(self, user_id, title=None):
        with connect() as conn:
            row = conn.execute(
                "insert into sessions (user_id, title) values (%s, %s) returning id", (user_id, title)
            ).fetchone()
        return str(row[0])

    def sessions(self, user_id, limit=20):
        with connect() as conn:
            rows = conn.execute(
                "select id, title, created_at from sessions where user_id = %s order by created_at desc limit %s",
                (user_id, limit),
            ).fetchall()
        return [{"id": str(r[0]), "title": r[1], "created_at": r[2].isoformat()} for r in rows]

    def set_title(self, session_id, title):
        with connect() as conn:
            conn.execute("update sessions set title = %s where id = %s", (title, session_id))

    def add_message(self, session_id, role, content, agent=None, trace_id=None, payload=None):
        with connect() as conn:
            conn.execute(
                "insert into messages (session_id, role, content, agent, trace_id, payload) "
                "values (%s, %s, %s, %s, %s, %s)",
                (session_id, role, content, agent, trace_id, jsonb(payload) if payload else None),
            )

    def messages(self, session_id, limit=20):
        with connect() as conn:
            rows = conn.execute(
                "select role, content, agent, payload from "
                "(select id, role, content, agent, payload from messages where session_id = %s "
                "order by id desc limit %s) m order by id",
                (session_id, limit),
            ).fetchall()
        return [{"role": r[0], "content": r[1], "agent": r[2], "payload": r[3]} for r in rows]

    def log_request(self, trace):
        with connect() as conn:
            conn.execute(
                "insert into request_logs (trace_id, session_id, question, agent, latency, prompt_tokens, "
                "completion_tokens, error, trace) values (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s) "
                "on conflict (trace_id) do nothing",
                (
                    trace["trace_id"],
                    trace.get("session_id"),
                    trace["question"],
                    trace.get("agent"),
                    trace["latency"],
                    trace["prompt_tokens"],
                    trace["completion_tokens"],
                    trace.get("error"),
                    jsonb(trace),
                ),
            )