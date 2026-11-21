from ticket_assistant.generator import check_citations, format_structured, generate, strip_unverified
from ticket_assistant.retriever import Retriever
from ticket_assistant.router import Router, vector_filters
from ticket_assistant.structured_store import Store

MIN_SCORE = 0.6
TOP_K = 4
OUT_OF_SCOPE = "I can only answer questions about the Kafka, Cassandra and Hadoop Jira tickets in this dataset."
NO_EVIDENCE = "I could not find tickets that answer this question."


def reply(plan, answer, sources=None, **extra):
    return {"route": plan["route"], "plan": plan, "answer": answer, "sources": sources or [], **extra}


class Assistant:
    def __init__(self):
        self.store = Store()
        self.router = Router(self.store)
        self.retriever = Retriever()

    def ask(self, question):
        try:
            plan = self.router.plan(question)
            return self.run(question, plan)
        except ValueError as e:
            return {
                "route": "error",
                "plan": None,
                "answer": f"I could not turn that question into a valid query: {e}",
                "sources": [],
            }

    def run(self, question, plan):
        route = plan["route"]
        if route == "out_of_scope":
            return reply(plan, OUT_OF_SCOPE)
        if route == "structured":
            result = self.store.query(plan)
            return reply(plan, format_structured(plan, result), sql=result["sql"], params=result["params"])
        hits = self.retriever.search(
            plan["search_query"], k=TOP_K, filters=vector_filters(plan["filters"]), per_ticket=1
        )
        hits = [h for h in hits if h["score"] >= MIN_SCORE]
        if not hits:
            return reply(plan, NO_EVIDENCE)
        text = generate(question, hits)
        cited, unverified = check_citations(text, hits)
        if unverified:
            text = strip_unverified(text, unverified)
        sources = [{"key": h["key"], "title": h["title"], "score": round(h["score"], 3)} for h in hits]
        return reply(plan, text, sources=sources, cited=cited, unverified=unverified)