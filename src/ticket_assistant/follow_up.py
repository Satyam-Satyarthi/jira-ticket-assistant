from ticket_assistant.llm import chat_json

SYSTEM = """You rewrite follow-up questions in a chat about Apache Jira tickets of Kafka, Cassandra and Hadoop.
Given the conversation and the latest question, return the latest question rewritten so that it can be understood without the conversation. Carry over only what the latest question refers to, such as the project, the topic or a filter it implies. Do not add a year or any other filter that the latest question does not imply, and do not keep a single year when the latest question asks for a breakdown per year. If the latest question is already complete, return it unchanged. Do not answer it.
Reply with one JSON object: {"question": "<rewritten question>"}."""


def transcript(messages):
    lines = []
    for m in messages:
        who = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{who}: {m['content'].replace(chr(10), ' ')[:300]}")
    return "\n".join(lines)


def rewrite(question, messages):
    if not messages:
        return question
    prompt = f"Conversation:\n{transcript(messages)}\n\nLatest question: {question}"
    raw, _ = chat_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        max_tokens=300,
    )
    text = raw.get("question")
    return text.strip() if isinstance(text, str) and text.strip() else question