import json
import re
import time
from pathlib import Path

import pandas as pd

from ticket_assistant.config import CHUNKS
from ticket_assistant.llm import chat

OUT = Path("eval/rag_set.jsonl")
PER_PROJECT = 10
KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
SYSTEM = (
    "You write search questions for an evaluation. Given an Apache Jira ticket, write one short search question "
    "(at most 20 words) that this ticket answers, phrased like a developer who has the problem and has not seen "
    "the ticket. Do not copy the title, and do not mention ticket keys or exact configuration names. "
    "Reply with the question only."
)
UNANSWERABLE = [
    "What did the Kafka team decide about rewriting the broker in Rust?",
    "Which Cassandra ticket added support for quantum computing?",
    "What was decided about migrating Hadoop to Python 4?",
    "Which Kafka ticket introduced a built-in chess engine?",
    "What is the Cassandra team's plan for a mobile app?",
    "Which Hadoop ticket added a blockchain storage layer?",
]

chunks = pd.read_json(CHUNKS, lines=True)
pool = chunks[(chunks.source == "description") & (chunks.text.str.split().str.len() >= 100)]
pool = pool.drop_duplicates("key")
items = []

for project in ["KAFKA", "CASSANDRA", "HADOOP"]:
    taken = 0
    for row in pool[pool.project == project].sample(PER_PROJECT * 2, random_state=11).itertuples():
        if taken == PER_PROJECT:
            break
        text = " ".join(row.text.split()[:150])
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Title: {row.title}\n\nTicket text: {text}"},
        ]
        answer, _ = chat(messages, max_tokens=200)
        time.sleep(4)
        question = answer.strip().strip('"')
        if not question.endswith("?") or KEY.search(question):
            continue
        taken += 1
        items.append(
            {
                "id": f"retrieval-{len(items) + 1:03d}",
                "type": "retrieval",
                "question": question,
                "expected_agent": "rag",
                "expected": row.key,
            }
        )

for question in UNANSWERABLE:
    items.append(
        {
            "id": f"refusal-{len(items) + 1:03d}",
            "type": "refusal",
            "question": question,
            "expected_agent": "rag",
            "expected": None,
        }
    )

with OUT.open("w", encoding="utf-8", newline="\n") as f:
    for item in items:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
print(len(items))