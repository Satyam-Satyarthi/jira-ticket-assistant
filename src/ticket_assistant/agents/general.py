from ticket_assistant.agents.base import Agent, result
from ticket_assistant.llm import chat

SYSTEM = (
    "You are a helpful assistant. Answer clearly in at most 150 words. "
    "If the question needs live data such as weather or news, say that you cannot look it up."
)
NOTE = "General answer from the language model. It is not based on the Jira tickets."


class GeneralAgent(Agent):
    name = "general"
    description = "Questions unrelated to Kafka, Cassandra, Hadoop and their tickets: general knowledge, how-to, explanations, small talk."
    
    def run(self, question, context):
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
        ]
        text, _ = chat(messages, max_tokens=500)
        return result(self, text.strip(), note=NOTE)