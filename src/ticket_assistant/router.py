from ticket_assistant.llm import chat_json

SYSTEM = """You route a user question to exactly one agent. Reply with one JSON object: {"agent": "<name>"}.

The data behind this assistant is Apache Jira tickets of Kafka, Cassandra and Hadoop.

Agents:
{agents}

Choose the agent whose description fits best. Technical questions about Kafka, Cassandra, Hadoop or the systems around them (distributed storage, messaging, data processing, JVM engineering problems) belong to the rag agent, even when the question names no project and does not mention tickets. Questions that ask which tickets mention, add, introduce or discuss something belong to the rag agent, because they depend on what the tickets say. The table agent is only for lists chosen or ordered by ticket fields such as dates, status, type or resolution time. Only questions unrelated to these systems belong to the general agent. Questions that ask for a percentage, ratio, share, growth, difference or any other calculation belong to the analysis agent, even when they follow a count question. Questions that compare two groups, such as how many more or fewer, how much larger or smaller, or by how much, are calculations and belong to the analysis agent."""

class Router:
    def __init__(self, registry):
        self.registry = registry
        self.system = SYSTEM.replace("{agents}", registry.describe())

    def route(self, question):
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": question},
        ]
        raw, _ = chat_json(messages, max_tokens=300)
        name = raw.get("agent")
        if name not in self.registry.agents:
            raise ValueError(f"unknown agent {name!r}")
        return name