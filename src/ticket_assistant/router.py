from ticket_assistant.llm import chat_json
from ticket_assistant.structured_store import BOOLEAN, CATEGORICAL, NUMERIC

ROUTES = {"structured", "semantic", "hybrid", "out_of_scope"}
VECTOR_FIELDS = {"project", "issue_type", "priority_group", "status", "outcome_group", "is_resolved", "created_year"}
PROMPT_FIELDS = ["project", "issue_type", "priority_group", "status", "outcome_group"]

SYSTEM = """You route questions about Apache Jira tickets (Kafka, Cassandra, Hadoop) and reply with one JSON object.

Routes:
- structured: counts or statistics that need only ticket fields
- semantic: what tickets say (causes, errors, discussions, fixes)
- hybrid: a semantic question restricted by ticket fields
- out_of_scope: anything else

JSON keys: route, metric, column, group_by, filters, search_query.
metric is one of count, avg, median, min, max, sum. Use count unless a numeric column is asked about.
column is null or one of resolution_days, open_age_days, component_count.
group_by is null or one of project, issue_type, priority_group, status, outcome_group, created_year.
filters is a list of {"column", "op", "value"}. op is "=", "in", ">", ">=", "<" or "<=". Filterable columns: project, issue_type, priority_group, status, outcome_group, is_resolved (true or false), created_year (a number).
search_query is a short keyword query for semantic and hybrid routes, otherwise null.
Add a filter only when the question states it. Never guess a filter.
Allowed values:
{values}

Examples:
Q: How many issues are of type Task?
{"route":"structured","metric":"count","column":null,"group_by":null,"filters":[{"column":"issue_type","op":"=","value":"Task"}],"search_query":null}
Q: Average resolution days per project for bugs?
{"route":"structured","metric":"avg","column":"resolution_days","group_by":"project","filters":[{"column":"issue_type","op":"=","value":"Bug"}],"search_query":null}
Q: Why do consumer group rebalances take so long?
{"route":"semantic","metric":"count","column":null,"group_by":null,"filters":[],"search_query":"consumer group rebalance slow"}
Q: Which unresolved Kafka bugs mention memory leaks?
{"route":"hybrid","metric":"count","column":null,"group_by":null,"filters":[{"column":"project","op":"=","value":"KAFKA"},{"column":"issue_type","op":"=","value":"Bug"},{"column":"is_resolved","op":"=","value":false}],"search_query":"memory leak"}
Q: Which unresolved Cassandra issues mention compaction stalls?
{"route":"hybrid","metric":"count","column":null,"group_by":null,"filters":[{"column":"project","op":"=","value":"CASSANDRA"},{"column":"is_resolved","op":"=","value":false}],"search_query":"compaction stall"}
Q: What is the capital of France?
{"route":"out_of_scope","metric":"count","column":null,"group_by":null,"filters":[],"search_query":null}
"""


def build_prompt(store):
    values = "\n".join(
        f"- {field}: {', '.join(sorted(store.values[field].values()))}"
        for field in PROMPT_FIELDS
    )
    return SYSTEM.replace("{values}", values)


def fix_filter(f, store):
    column = f.get("column")
    value = f.get("value")
    op = f.get("op", "=")
    if column in CATEGORICAL:
        items = value if isinstance(value, list) else [value]
        fixed = [store.values[column].get(str(v).lower()) for v in items]
        if not fixed or None in fixed:
            raise ValueError(f"unknown value {value!r} for {column}")
        if len(fixed) == 1:
            return {"column": column, "op": "=", "value": fixed[0]}
        return {"column": column, "op": "in", "value": fixed}
    if column in BOOLEAN:
        if isinstance(value, str):
            value = value.strip().lower() == "true"
        return {"column": column, "op": "=", "value": bool(value)}
    if column in NUMERIC:
        number = int(value) if column == "created_year" else float(value)
        return {"column": column, "op": op, "value": number}
    raise ValueError(f"cannot filter on {column!r}")


def clean(plan, store):
    route = plan.get("route")
    if route not in ROUTES:
        raise ValueError(f"unknown route {route!r}")
    if route in ("semantic", "hybrid") and not plan.get("search_query"):
        raise ValueError("missing search query")
    return {
        "route": route,
        "metric": plan.get("metric") or "count",
        "column": plan.get("column"),
        "group_by": plan.get("group_by"),
        "filters": [fix_filter(f, store) for f in plan.get("filters") or []],
        "search_query": plan.get("search_query"),
    }


def vector_filters(filters):
    out = {}
    for f in filters:
        if f["column"] not in VECTOR_FIELDS or f["op"] not in ("=", "in"):
            raise ValueError(f"{f['column']} filters are not supported for text search yet")
        out[f["column"]] = f["value"]
    return out


class Router:
    def __init__(self, store):
        self.store = store
        self.system = build_prompt(store)

    def plan(self, question):
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": question},
        ]
        raw, _ = chat_json(messages, max_tokens=250)
        return clean(raw, self.store)