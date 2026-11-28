import json
import re
import statistics
from collections import Counter
from pathlib import Path

RESULTS = Path("eval/results/run.jsonl")
SUMMARY = Path("eval/results/summary.json")
TOLERANCE = 0.01
REFUSAL = re.compile(
    r"do not|does not|don't|doesn't|no mention|not mention|could not find|cannot find|not contain|not address|no information",
    re.I,
)


def load():
    latest = {}
    with RESULTS.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            latest[row["id"]] = row
    return list(latest.values())


def of(rows, kind):
    return [r for r in rows if r["type"] == kind]


def rate(flags):
    return round(sum(flags) / len(flags), 3) if flags else None


def close(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) <= TOLERANCE


def count_ok(r):
    data = r["data"]
    return bool(data) and len(data) == 1 and close(data[0]["value"], r["expected"])


def table_ok(r):
    return r["data"] == r["expected"]


def table_overlap(r):
    got, want = r["data"] or [], r["expected"]
    return len(set(got) & set(want)) / len(want)


def chart_ok(r):
    got, want = r["data"], r["expected"]
    if not got or set(got) != set(want):
        return False
    return all(close(got[k], want[k]) for k in want)

def math_ok(r):
    data, want = r["data"], r["expected"]
    if not isinstance(data, dict):
        return False
    if isinstance(want, dict):
        if data.get("kind") != "table":
            return False
        found = {str(row[0]): [v for v in row[1:] if isinstance(v, (int, float))] for row in data["rows"]}
        return all(any(close(v, want[k]) for v in found.get(k, [])) for k in want)
    return data.get("kind") == "scalar" and close(data.get("value"), want)


def routing(rows):
    by_type = {}
    for r in rows:
        by_type.setdefault(r["type"], []).append(r["agent"] == r["expected_agent"])
    result = {"overall": rate([r["agent"] == r["expected_agent"] for r in rows])}
    result.update({kind: rate(flags) for kind, flags in by_type.items()})
    return result


def retrieval(rows):
    ranks = []
    for r in rows:
        ranked = (r["data"] or {}).get("ranked", [])
        ranks.append(ranked.index(r["expected"]) + 1 if r["expected"] in ranked else None)

    def hit(k):
        return rate([x is not None and x <= k for x in ranks])

    mrr = round(sum(1 / x for x in ranks if x) / len(ranks), 3) if ranks else None
    sources = [(r["data"] or {}).get("sources", []) for r in rows]
    return {
        "n": len(rows),
        "hit@1": hit(1),
        "hit@4": hit(4),
        "hit@10": hit(10),
        "mrr": mrr,
        "source_in_final_sources": rate([r["expected"] in s for r, s in zip(rows, sources)]),
        "no_evidence_answers": rate([not s for s in sources]),
    }


def refusal(rows):
    flags = []
    for r in rows:
        sources = (r["data"] or {}).get("sources", [])
        flags.append(not sources or bool(REFUSAL.search(r["answer"])))
    return {"n": len(rows), "refused": rate(flags)}


def citations(rows):
    answered = [r for r in rows if (r["data"] or {}).get("sources")]
    return {
        "answered": len(answered),
        "with_unverified_key": sum(1 for r in answered if r["data"].get("unverified")),
        "without_any_citation": sum(1 for r in answered if not r["data"].get("cited")),
    }


def operations(rows):
    latency = sorted(r["latency"] for r in rows if r.get("latency") is not None)
    tokens = [r["tokens"] for r in rows if r.get("tokens") is not None]
    providers = Counter(p for r in rows for p in r.get("providers") or [])
    return {
        "median_latency_s": round(statistics.median(latency), 2),
        "p95_latency_s": round(latency[int(0.95 * (len(latency) - 1))], 2),
        "mean_tokens_per_question": round(statistics.mean(tokens)),
        "llm_calls_by_provider": dict(providers),
        "errors": sum(1 for r in rows if r["agent"] == "error"),
    }


def failures(rows):
    out = []
    for r in rows:
        if r["agent"] != r["expected_agent"]:
            out.append(f"routing {r['id']}: expected {r['expected_agent']}, got {r['agent']}: {r['question']}")
    for r in of(rows, "count"):
        if not count_ok(r):
            out.append(f"count {r['id']}: {r['question']} expected {r['expected']} got {r['data']}")
    for r in of(rows, "table"):
        if not table_ok(r):
            out.append(f"table {r['id']}: {r['question']}")
    for r in of(rows, "chart"):
        if not chart_ok(r):
            out.append(f"chart {r['id']}: {r['question']}")
    for r in of(rows, "math"):
        if not math_ok(r):
            out.append(f"math {r['id']}: {r['question']} expected {r['expected']} got {r['data']}")
    return out


def main():
    rows = load()
    tables = of(rows, "table")
    summary = {
        "questions": len(rows),
        "routing_accuracy": routing(rows),
        "count_exact_match": rate([count_ok(r) for r in of(rows, "count")]),
        "table_exact_order": rate([table_ok(r) for r in tables]),
        "table_mean_overlap": round(statistics.mean(table_overlap(r) for r in tables), 3),
        "chart_exact_match": rate([chart_ok(r) for r in of(rows, "chart")]),
        "math_exact_match": rate([math_ok(r) for r in of(rows, "math")]),
        "retrieval": retrieval(of(rows, "retrieval")),
        "refusal": refusal(of(rows, "refusal")),
        "citations": citations(of(rows, "rag") + of(rows, "retrieval")),
        "operations": operations(rows),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for line in failures(rows):
        print(line)


if __name__ == "__main__":
    main()