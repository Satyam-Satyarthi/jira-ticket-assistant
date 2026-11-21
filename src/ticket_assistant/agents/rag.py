from ticket_assistant.agents.base import Agent, result
from ticket_assistant.generator import check_citations, generate, strip_unverified
from ticket_assistant.llm import chat_json
from ticket_assistant.planning import FILTER_RULES, clean_filters, value_lines, vector_filters

MIN_SCORE = 0.6
TOP_K = 4
NO_EVIDENCE = "I could not find tickets that answer this question."

SYSTEM = """You turn a question about Apache Jira tickets into a search plan. Reply with one JSON object.

Keys: search_query, filters.
search_query is a short keyword query for what the tickets should talk about.
{filter_rules}

Allowed values:
{values}

Examples:
Q: Why do consumer group rebalances take so long?
{"search_query":"consumer group rebalance slow","filters":[]}
Q: Which unresolved Kafka bugs mention memory leaks?
{"search_query":"memory leak","filters":[{"column":"project","op":"=","value":"KAFKA"},{"column":"issue_type","op":"=","value":"Bug"},{"column":"is_resolved","op":"=","value":false}]}
Q: Which unresolved Cassandra issues mention compaction stalls?
{"search_query":"compaction stall","filters":[{"column":"project","op":"=","value":"CASSANDRA"},{"column":"is_resolved","op":"=","value":false}]}
"""


class RagAgent(Agent):
    name = "rag"
    description = (
        "Questions about problems, errors, causes, behaviour, fixes or workarounds in Kafka, Cassandra or Hadoop, "
        "answered from what the tickets say, optionally limited to a project, type, status or year."
    )

    def run(self, question, context):
        system = SYSTEM.replace("{filter_rules}", FILTER_RULES).replace("{values}", value_lines(context.store))
        messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
        raw, _ = chat_json(messages, max_tokens=400)
        query = raw.get("search_query")
        if not query:
            raise ValueError("missing search query")
        filters = clean_filters(raw.get("filters"), context.store)
        plan = {"search_query": query, "filters": filters}
        hits = context.retriever.search(query, k=TOP_K, filters=vector_filters(filters), per_ticket=1)
        hits = [h for h in hits if h["score"] >= MIN_SCORE]
        if not hits:
            return result(self, NO_EVIDENCE, plan=plan, sources=[])
        text = generate(question, hits)
        cited, unverified = check_citations(text, hits)
        if unverified:
            text = strip_unverified(text, unverified)
        sources = [{"key": h["key"], "title": h["title"], "score": round(h["score"], 3)} for h in hits]
        return result(self, text, plan=plan, sources=sources, cited=cited, unverified=unverified)