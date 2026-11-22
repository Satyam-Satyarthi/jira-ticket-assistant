import json
import random
from pathlib import Path

import pandas as pd

from ticket_assistant.config import ISSUES_CSV

OUT = Path("eval/eval_set.jsonl")
NAMES = {"KAFKA": "Kafka", "CASSANDRA": "Cassandra", "HADOOP": "Hadoop"}

GENERAL = [
    "What is the capital of France?",
    "How can a spacecraft reach the moon?",
    "Explain what a REST API is.",
    "Write a haiku about autumn.",
    "Convert 100 degrees Fahrenheit to Celsius.",
    "Who wrote Pride and Prejudice?",
    "Give me three tips for a job interview.",
    "How do I reverse a string in Python?",
    "What is the difference between a stock and a bond?",
    "Translate good morning into Spanish.",
]
RAG = [
    "Why do consumer group rebalances take so long?",
    "What causes NameNode out-of-memory errors?",
    "How do people work around slow compactions in Cassandra?",
    "Has anyone reported data loss after an unclean leader election in Kafka?",
    "What errors happen when HDFS blocks are corrupted?",
    "Why do Cassandra nodes get marked down incorrectly by gossip?",
    "What problems have been reported with Kafka log cleanup?",
    "Why does the Hadoop ResourceManager run out of memory?",
    "What causes timeouts when a Kafka producer connects to a broker?",
    "Why do Cassandra repairs take so long?",
    "How are duplicate messages handled in Kafka consumers?",
    "What causes slow block reports in HDFS?",
]

random.seed(7)
d = pd.read_csv(ISSUES_CSV)
d["created_date"] = d["created"].astype(str).str[:10]
d["created_year"] = pd.to_datetime(d["created"], errors="coerce").dt.year.astype("Int64")
valid = d[d["valid_for_duration"]]
items = []


def add(kind, question, agent, expected=None):
    items.append(
        {
            "id": f"{kind}-{len(items) + 1:03d}",
            "type": kind,
            "question": question,
            "expected_agent": agent,
            "expected": expected,
        }
    )


def per(frame, column):
    return {str(k): int(v) for k, v in frame.groupby(column).size().items()}


add("count", "How many issues are in the dataset in total?", "count", len(d))
for p, n in NAMES.items():
    add("count", f"How many {n} issues are there?", "count", int((d.project == p).sum()))
for t in d.issue_type.value_counts().index[:4]:
    p = random.choice(list(NAMES))
    mask = (d.project == p) & (d.issue_type == t)
    add("count", f"How many {t} issues does {NAMES[p]} have?", "count", int(mask.sum()))
for p, n in NAMES.items():
    add("count", f"How many {n} issues are unresolved?", "count", int(((d.project == p) & ~d.is_resolved).sum()))
for p, n in NAMES.items():
    year = random.choice(range(2012, 2025))
    mask = (d.project == p) & (d.created_year == year)
    add("count", f"How many {n} issues were created in {year}?", "count", int(mask.sum()))
for p, n in NAMES.items():
    x = valid[(valid.project == p) & (valid.issue_type == "Bug")]
    add("count", f"What is the average resolution time in days for {n} bugs?", "count", round(float(x.resolution_days.mean()), 2))
for p in ["KAFKA", "HADOOP"]:
    x = valid[valid.project == p]
    add("count", f"What is the median resolution time in days for {NAMES[p]} issues?", "count", round(float(x.resolution_days.median()), 2))

for p in ["KAFKA", "CASSANDRA"]:
    x = d[(d.project == p) & ~d.is_resolved].sort_values(["created_date", "key"]).head(10)
    add("table", f"List the 10 oldest unresolved {NAMES[p]} issues", "table", x.key.tolist())
for p, n in NAMES.items():
    x = valid[valid.project == p].sort_values(["resolution_days", "key"], ascending=[False, True]).head(5)
    add("table", f"Show the 5 {n} issues that took longest to resolve", "table", x.key.tolist())
for p, n in NAMES.items():
    x = d[d.project == p].sort_values(["created_date", "key"], ascending=[False, True]).head(5)
    add("table", f"Show the 5 newest {n} issues", "table", x.key.tolist())
x = d[(d.project == "HADOOP") & (d.issue_type == "Bug") & ~d.is_resolved]
x = x.sort_values(["created_date", "key"]).head(5)
add("table", "List the 5 oldest open Hadoop bugs", "table", x.key.tolist())

add("chart", "Plot the number of issues per project", "chart", per(d, "project"))
for p, n in NAMES.items():
    add("chart", f"Chart {n} issues created per year", "chart", per(d[d.project == p], "created_year"))
add("chart", "Show a bar chart of issues by issue type", "chart", per(d, "issue_type"))
average = {p: round(float(g.resolution_days.mean()), 2) for p, g in valid.groupby("project")}
add("chart", "Chart the average resolution days per project", "chart", average)

for q in RAG:
    add("rag", q, "rag")
for q in GENERAL:
    add("general", q, "general")

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8", newline="\n") as f:
    for item in items:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
print(pd.Series([i["type"] for i in items]).value_counts())