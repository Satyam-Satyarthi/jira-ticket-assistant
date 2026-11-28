from ticket_assistant.structured_store import BOOLEAN, CATEGORICAL, NUMERIC

VECTOR_FIELDS = {"project", "issue_type", "priority_group", "status", "outcome_group", "is_resolved", "created_year"}
PROMPT_FIELDS = ["project", "issue_type", "priority_group", "status", "outcome_group"]

FILTER_RULES = (
    'filters is a list of {"column", "op", "value"}. op is "=", "in", ">", ">=", "<" or "<=". '
    "Filterable columns: project, issue_type, priority_group, status, outcome_group, "
    "is_resolved (true or false), created_year (a number).\n"
    "Add a filter only when the question states it. Never guess a filter. "
    "When the question names a project (Kafka, Cassandra or Hadoop), always add a project filter for it."
)


def value_lines(store):
    return "\n".join(
        f"- {field}: {', '.join(sorted(store.values[field].values()))}" for field in PROMPT_FIELDS
    )


def fix_filter(f, store):
    if not isinstance(f, dict):
        raise ValueError("filter must be an object")
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
        cast = int if column == "created_year" else float
        try:
            if isinstance(value, list):
                return {"column": column, "op": "in", "value": [cast(v) for v in value]}
            if op == "in":
                return {"column": column, "op": "in", "value": [cast(value)]}
            return {"column": column, "op": op, "value": cast(value)}
        except (TypeError, ValueError) as e:
            raise ValueError(f"{column} needs a number") from e
    raise ValueError(f"cannot filter on {column!r}")


def clean_filters(filters, store):
    return [fix_filter(f, store) for f in filters or []]


def vector_filters(filters):
    out = {}
    for f in filters:
        if f["column"] not in VECTOR_FIELDS or f["op"] not in ("=", "in"):
            raise ValueError(f"{f['column']} filters are not supported for text search yet")
        out[f["column"]] = f["value"]
    return out