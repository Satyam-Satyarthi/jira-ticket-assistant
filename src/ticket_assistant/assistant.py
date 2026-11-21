from ticket_assistant.agents import build_registry
from ticket_assistant.agents.base import Context
from ticket_assistant.retriever import Retriever
from ticket_assistant.router import Router
from ticket_assistant.structured_store import Store


class Assistant:
    def __init__(self):
        self.registry = build_registry()
        self.context = Context(store=Store(), retriever=Retriever())
        self.router = Router(self.registry)

    def ask(self, question):
        try:
            name = self.router.route(question)
            return self.registry.get(name).run(question, self.context)
        except (ValueError, RuntimeError) as e:
            return {"agent": "error", "answer": f"I could not answer that: {e}", "sources": []}