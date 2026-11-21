import json

import plotly.graph_objects as go

from ticket_assistant.agents.base import Agent, result
from ticket_assistant.agents.count import LABELS, number
from ticket_assistant.llm import chat_json
from ticket_assistant.planning import FILTER_RULES, clean_filters, value_lines

KINDS = {"bar", "line", "pie"}

SYSTEM = """You turn a request for a chart about Apache Jira tickets into a JSON query plan. Reply with one JSON object.

Keys: chart, metric, column, group_by, filters.
chart is one of bar, line, pie. Use line for trends over created_year, otherwise bar unless a pie is asked for.
metric is one of count, avg, median, min, max, sum. Use count unless a numeric column is asked about.
column is null or one of resolution_days, open_age_days, component_count.
group_by is required and is one of project, issue_type, priority_group, status, outcome_group, created_year.
{filter_rules}

Allowed values:
{values}

Examples:
Q: Plot the number of issues per project
{"chart":"bar","metric":"count","column":null,"group_by":"project","filters":[]}
Q: Chart Kafka issues created per year
{"chart":"line","metric":"count","column":null,"group_by":"created_year","filters":[{"column":"project","op":"=","value":"KAFKA"}]}
"""


def title_of(plan):
    if plan["metric"] == "count":
        text = "Number of issues"
    else:
        text = f"{LABELS[plan['metric']].capitalize()} {plan['column']}"
    if plan["filters"]:
        text += " where " + " and ".join(f"{f['column']} {f['op']} {f['value']}" for f in plan["filters"])
    return f"{text}, by {plan['group_by']}"


def figure(plan, rows, title):
    group = plan["group_by"]
    x = [str(r[group]) for r in rows]
    y = [r["value"] for r in rows]
    if plan["chart"] == "pie":
        trace = go.Pie(labels=x, values=y)
    elif plan["chart"] == "line":
        trace = go.Scatter(x=x, y=y, mode="lines+markers")
    else:
        trace = go.Bar(x=x, y=y)
    fig = go.Figure(trace)
    fig.update_layout(title=title, xaxis_title=group, yaxis_title=plan["column"] or "issues")
    return json.loads(fig.to_json())


class ChartAgent(Agent):
    name = "chart"
    description = (
        "Charts, plots or graphs comparing counts or averages across projects, types, statuses, "
        "priorities or years."
    )

    def run(self, question, context):
        system = SYSTEM.replace("{filter_rules}", FILTER_RULES).replace("{values}", value_lines(context.store))
        messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
        raw, _ = chat_json(messages, max_tokens=400)
        group = raw.get("group_by")
        if not group:
            raise ValueError("a chart needs a grouping such as project or year")
        kind = raw.get("chart")
        if kind not in KINDS:
            kind = "line" if group == "created_year" else "bar"
        plan = {
            "chart": kind,
            "metric": raw.get("metric") or "count",
            "column": raw.get("column"),
            "group_by": group,
            "filters": clean_filters(raw.get("filters"), context.store),
        }
        out = context.store.query(plan)
        rows = out["rows"]
        if not rows:
            return result(self, "No matching issues.", plan=plan)
        title = title_of(plan)
        top = max(rows, key=lambda r: r["value"] or 0)
        low = min(rows, key=lambda r: r["value"] or 0)
        answer = (
            f"{title}. Highest: {top[group]} ({number(top['value'])}); "
            f"lowest: {low[group]} ({number(low['value'])})."
        )
        return result(self, answer, plan=plan, figure=figure(plan, rows, title), sql=out["sql"], params=out["params"])