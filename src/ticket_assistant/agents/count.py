from ticket_assistant.agents.base import Agent, result
from ticket_assistant.llm import chat_json
from ticket_assistant.planning import FILTER_RULES, clean_filters, value_lines

LABELS = {"avg": "average", "median": "median", "min": "minimum", "max": "maximum", "sum": "total"}

SYSTEM = """You turn a question about Apache Jira tickets into a JSON query plan. Reply with one JSON object.

Keys: metric, column, group_by, filters.
metric is one of count, avg, median, min, max, sum. Use count unless a numeric column is asked about.
column is null or one of resolution_days, open_age_days, component_count.
group_by is null or one of project, issue_type, priority_group, status, outcome_group, created_year.
{filter_rules}

Allowed values:
{values}

Examples:
Q: How many issues are of type Task?
{"metric":"count","column":null,"group_by":null,"filters":[{"column":"issue_type","op":"=","value":"Task"}]}
Q: Average resolution days per project for bugs?
{"metric":"avg","column":"resolution_days","group_by":"project","filters":[{"column":"issue_type","op":"=","value":"Bug"}]}
Q: How many Cassandra issues were created in 2024?
{"metric":"count","column":null,"group_by":null,"filters":[{"column":"project","op":"=","value":"CASSANDRA"},{"column":"created_year","op":"=","value":2024}]}
"""


def condition(f):
    value = ", ".join(f["value"]) if isinstance(f["value"], list) else f["value"]
    return f"{f['column']} {f['op']} {value}"


def number(value):
    return "n/a" if value is None else f"{value:,}"


def subject(plan):
    if plan["metric"] == "count":
        text = "The number of issues"
    else:
        text = f"The {LABELS[plan['metric']]} {plan['column']} of issues"
    if plan["filters"]:
        text += " where " + " and ".join(condition(f) for f in plan["filters"])
    return text


def render(plan, rows):
    head = subject(plan)
    group = plan["group_by"]
    note = " (valid durations only)" if plan["column"] == "resolution_days" else ""
    if not group:
        value = rows[0]["value"] if rows else None
        if value is None:
            return f"{head} cannot be computed: no matching issues."
        return f"{head} is **{number(value)}**{note}."
    if not rows:
        return f"{head}, by {group}: no matching issues."
    lines = [f"{head}, by {group}{note}:", ""]
    lines += [f"- {r[group]}: **{number(r['value'])}**" for r in rows]
    return "\n".join(lines)


class CountAgent(Agent):
    name = "count"
    description = (
        "Exact numbers about tickets answered as text: counts, averages, medians, minimums, maximums or totals, "
        "optionally per project, type, status, priority or year. Not for charts or lists of tickets."
        "Not for percentages, ratios or other calculations."
    )

    def run(self, question, context):
        system = SYSTEM.replace("{filter_rules}", FILTER_RULES).replace("{values}", value_lines(context.store))
        messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
        raw, _ = chat_json(messages, max_tokens=400)
        plan = {
            "metric": raw.get("metric") or "count",
            "column": raw.get("column"),
            "group_by": raw.get("group_by"),
            "filters": clean_filters(raw.get("filters"), context.store),
        }
        out = context.store.query(plan)
        return result(self, render(plan, out["rows"]), plan=plan, data=out["rows"], sql=out["sql"], params=out["params"])