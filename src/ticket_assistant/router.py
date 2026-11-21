from ticket_assistant.llm import chat_json

SYSTEM = """You route a user question to exactly one agent. Reply with one JSON object: {"agent": "<name>"}.

The data behind this assistant is Apache Jira tickets of Kafka, Cassandra and Hadoop.

Agents:
{agents}

Choose the agent whose description fits best. Technical questions about Kafka, Cassandra or Hadoop belong to an agent that uses the tickets, even when the question does not mention tickets. Only questions unrelated to these systems belong to the general agent."""

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