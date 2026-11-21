import logging

import psycopg

from ticket_assistant.agents import build_registry
from ticket_assistant.agents.base import Context
from ticket_assistant.config import DATABASE_URL
from ticket_assistant.follow_up import rewrite
from ticket_assistant.history import History
from ticket_assistant.retriever import Retriever
from ticket_assistant.router import Router
from ticket_assistant.structured_store import Store
from ticket_assistant.trace import finish, start

log = logging.getLogger(__name__)
PAYLOAD_KEYS = ("plan", "sources", "table", "figure", "note", "cited", "unverified")


class Assistant:
    def __init__(self):
        self.registry = build_registry()
        self.context = Context(store=Store(), retriever=Retriever())
        self.router = Router(self.registry)
        self.history = History() if DATABASE_URL else None

    def prior(self, session_id):
        if not (self.history and session_id):
            return []
        try:
            return self.history.messages(session_id, limit=6)
        except psycopg.Error as e:
            log.warning("history read failed: %s", e)
            return []

    def save(self, session_id, question, out, trace, first):
        if not self.history:
            return
        try:
            self.history.log_request(trace)
            if not session_id:
                return
            if first:
                self.history.set_title(session_id, question[:60])
            self.history.add_message(session_id, "user", question)
            payload = {k: out[k] for k in PAYLOAD_KEYS if k in out}
            self.history.add_message(session_id, "assistant", out["answer"], out["agent"], trace["trace_id"], payload)
        except psycopg.Error as e:
            log.warning("history write failed: %s", e)

    def ask(self, question, session_id=None):
        trace = start(question, session_id)
        prior = self.prior(session_id)
        standalone = question
        error = None
        try:
            standalone = rewrite(question, prior)
            name = self.router.route(standalone)
            trace["agent"] = name
            out = self.registry.get(name).run(standalone, self.context)
        except (ValueError, RuntimeError) as e:
            error = str(e)
            out = {
                "agent": "error",
                "answer": f"I could not answer that: {error}. Please rephrase it, or ask one question at a time.",
                "sources": [],
            }
        out["trace_id"] = trace["trace_id"]
        finish(
            trace,
            plan=out.get("plan"),
            sources=[s["key"] for s in out.get("sources", [])],
            unverified=out.get("unverified"),
            answer=out["answer"],
            rewritten=standalone if standalone != question else None,
            error=error,
        )
        self.save(session_id, question, out, trace, first=not prior)
        return out