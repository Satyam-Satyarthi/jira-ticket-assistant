import json
import time
from pathlib import Path

from tqdm import tqdm

from ticket_assistant.assistant import Assistant

SETS = [Path("eval/eval_set.jsonl"), Path("eval/rag_set.jsonl"), Path("eval/math_set.jsonl")]
RESULTS = Path("eval/results/run.jsonl")
PAUSE = 15


def load_items():
    items = []
    for path in SETS:
        with path.open(encoding="utf-8") as f:
            items.extend(json.loads(line) for line in f)
    return items


def finished():
    if not RESULTS.exists():
        return set()
    with RESULTS.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return {r["id"] for r in rows if r["agent"] != "error"}


def extract(item, out, assistant):
    kind = item["type"]
    if kind == "count":
        return out.get("data")
    if kind == "table":
        return [r["key"] for r in (out.get("table") or {}).get("rows", [])]
    if kind == "chart":
        figure = out.get("figure")
        if not figure:
            return None
        trace = figure["data"][0]
        labels = trace.get("x") or trace.get("labels")
        values = trace.get("y") or trace.get("values")
        return dict(zip(labels, values))
    if kind == "math":
        return out.get("data")
    if kind in ("rag", "retrieval", "refusal"):
        data = {
            "sources": [s["key"] for s in out.get("sources", [])],
            "cited": out.get("cited"),
            "unverified": out.get("unverified"),
            "retrieved": out.get("retrieved"),
        }
        if kind == "retrieval":
            hits = assistant.context.retriever.search(item["question"], k=10, per_ticket=1)
            data["ranked"] = [h["key"] for h in hits]
        return data
    return None


def main():
    assistant = Assistant()
    done = finished()
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    todo = [i for i in load_items() if i["id"] not in done]
    with RESULTS.open("a", encoding="utf-8", newline="\n") as f:
        for item in tqdm(todo, desc="Evaluating", unit="question"):
            try:
                out = assistant.ask(item["question"])
                record = {
                    **item,
                    "agent": out["agent"],
                    "answer": out["answer"],
                    "plan": out.get("plan"),
                    "data": extract(item, out, assistant),
                    "latency": out.get("latency"),
                    "tokens": out.get("tokens"),
                    "providers": out.get("providers"),
                }
            except Exception as e:
                record = {**item, "agent": "error", "answer": str(e), "data": None}
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            f.flush()
            time.sleep(PAUSE)


if __name__ == "__main__":
    main()