import re

from ticket_assistant.llm import chat

KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
DASH = re.compile(r"\b([A-Z][A-Z0-9]+)[\u2010\u2011\u2012\u2013\u2212](\d+)\b")

SYSTEM = (
    "You answer questions about Apache Jira tickets using only the tickets provided. "
    "Describe what each ticket reports and cite its key in square brackets, exactly as written in the tickets. "
    "Do not state general causes, settings or conclusions that the tickets do not state. "
    "When asked which tickets match, list each relevant ticket key with a short reason. "
    "Use at most 120 words. If the tickets do not answer the question, say that they do not."
)

def context_block(hits):
    return "\n\n".join(f"[{h['key']}] {h['title']}\n{h['text']}" for h in hits)


def generate(question, hits):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Tickets:\n{context_block(hits)}\n\nQuestion: {question}"},
    ]
    text, _ = chat(messages, max_tokens=500)
    return DASH.sub(r"\1-\2", text.strip()).replace("【", "[").replace("】", "]")


def check_citations(text, hits):
    allowed = {h["key"] for h in hits}
    cited = list(dict.fromkeys(KEY.findall(text)))
    return [k for k in cited if k in allowed], [k for k in cited if k not in allowed]


def strip_unverified(text, unverified):
    for key in unverified:
        text = text.replace(f"[{key}]", "")
    return re.sub(r"[ ]{2,}", " ", text).strip()