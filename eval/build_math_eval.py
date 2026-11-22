import json
from pathlib import Path

import pandas as pd

from ticket_assistant.config import ISSUES_CSV

OUT = Path("eval/math_set.jsonl")
d = pd.read_csv(ISSUES_CSV)
d["created_year"] = pd.to_datetime(d["created"], errors="coerce").dt.year.astype("Int64")
valid = d[d["valid_for_duration"]]
count = d.groupby("project").size()
items = []


def add(question, expected):
    items.append(
        {
            "id": f"math-{len(items) + 1:03d}",
            "type": "math",
            "question": question,
            "expected_agent": "analysis",
            "expected": expected,
        }
    )


def pct(x):
    return round(float(x) * 100, 2)


def per(series):
    return {str(k): float(v) for k, v in series.items()}


add("What percentage of all issues are resolved?", pct(d.is_resolved.mean()))
add("What percentage of Hadoop issues are bugs?", pct((d[d.project == "HADOOP"].issue_type == "Bug").mean()))
add("What is the ratio of Kafka issues to Cassandra issues?", round(float(count["KAFKA"] / count["CASSANDRA"]), 2))
add("How many more Kafka issues are there than Hadoop issues?", float(count["KAFKA"] - count["HADOOP"]))
mean = valid[valid.issue_type == "Bug"].groupby("project").resolution_days.mean()
add(
    "By how many days does the average resolution time of Hadoop bugs exceed that of Kafka bugs?",
    round(float(mean["HADOOP"] - mean["KAFKA"]), 2),
)
n = d[d.project == "CASSANDRA"].groupby("created_year").size()
add(
    "By what percentage did the number of Cassandra issues created change from 2022 to 2023?",
    round(float((n[2023] / n[2022] - 1) * 100), 2),
)
add("What share of all issues does each project account for, in percent?", per((count / count.sum() * 100).round(2)))
bugs = d.assign(bug=d.issue_type == "Bug").groupby("project").bug.mean() * 100
add("What percentage of the issues of each project are bugs?", per(bugs.round(2)))
c = d[d.project == "CASSANDRA"]
add("What is the ratio of unresolved to resolved Cassandra issues?", round(float((~c.is_resolved).sum() / c.is_resolved.sum()), 2))
v = valid[["component_count", "resolution_days"]].dropna()
add(
    "What is the correlation between component count and resolution days across issues with valid durations?",
    round(float(v.component_count.corr(v.resolution_days)), 2),
)
NAMES = {"KAFKA": "Kafka", "CASSANDRA": "Cassandra", "HADOOP": "Hadoop"}
add("How many fewer Hadoop issues are there than Cassandra issues?", float(count["CASSANDRA"] - count["HADOOP"]))
k = d[d.project == "KAFKA"].groupby("created_year").size()
add(
    "By what percentage did the number of Kafka issues created change from 2023 to 2024?",
    round(float((k[2024] / k[2023] - 1) * 100), 2),
)
a, b = sorted(["KAFKA", "CASSANDRA"], key=lambda p: -mean[p])
add(
    f"By how many days does the average resolution time of {NAMES[a]} bugs exceed that of {NAMES[b]} bugs?",
    round(float(mean[a] - mean[b]), 2),
)
share = d.groupby("project").is_resolved.mean()
a, b = sorted(["KAFKA", "CASSANDRA"], key=lambda p: -share[p])
add(
    f"How many percentage points higher is the resolved share of {NAMES[a]} issues than that of {NAMES[b]} issues?",
    pct(share[a] - share[b]),
)
h = d[d.project == "HADOOP"].groupby("created_year").size()
add(
    "What is the percentage change in Hadoop issues created between 2021 and 2022?",
    round(float((h[2022] / h[2021] - 1) * 100), 2),
)
add(
    "Compared with 2018, by what percentage did the number of Kafka issues created in 2019 change?",
    round(float((k[2019] / k[2018] - 1) * 100), 2),
)

with OUT.open("w", encoding="utf-8", newline="\n") as f:
    for item in items:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")