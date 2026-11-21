import re

from ticket_assistant.llm import chat

KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
LABELS = {"avg": "Average", "median": "Median", "min": "Minimum", "max": "Maximum", "sum": "Total"}
SYSTEM = (
    "You answer questions about Apache Jira tickets using only the tickets provided. "
    "Cite ticket keys exactly as they appear in the tickets, in square brackets after each claim. "
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
    text, _ = chat(messages, max_tokens=220)
    return text.strip()


def check_citations(text, hits):
    allowed = {h["key"] for h in hits}
    cited = list(dict.fromkeys(KEY.findall(text)))
    return [k for k in cited if k in allowed], [k for k in cited if k not in allowed]

def strip_unverified(text, unverified):
    for key in unverified:
        text = text.replace(f"[{key}]", "")
    return re.sub(r"[ ]{2,}", " ", text).strip()

def number(value):
    return "n/a" if value is None else f"{value:,}"


def format_structured(plan, result):
    rows = result["rows"]
    metric = plan["metric"]
    label = "Issues" if metric == "count" else f"{LABELS[metric]} {plan['column']}"
    if plan["column"] == "resolution_days":
        label += " (valid durations only)"
    group = plan["group_by"]
    if not group:
        if not rows or rows[0]["value"] is None:
            return "No matching issues."
        return f"{label}: {number(rows[0]['value'])}"
    if not rows:
        return "No matching issues."
    lines = [f"{label} by {group}:"]
    lines += [f"- {r[group]}: {number(r['value'])}" for r in rows]
    return "\n".join(lines)