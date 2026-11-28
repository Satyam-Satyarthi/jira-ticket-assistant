import json

from ticket_assistant import sandbox
from ticket_assistant.agents.base import Agent, result
from ticket_assistant.llm import chat_json
from ticket_assistant.planning import value_lines

SYSTEM = """You answer calculation questions about Apache Jira tickets by writing pandas code. Reply with one JSON object with the keys label and code.

The code runs on a pandas DataFrame called df with one row per ticket. You may use only df, pd, np and math. Do not import anything, do not read or write files, and do not use df.query or df.eval. Use boolean masks.
Assign the final answer to the variable result. It must be a number, a short string, or a DataFrame or Series with clear column names. Round numbers to 2 decimals. Express percentages from 0 to 100.
Answer exactly what is asked. If the question names specific years, projects or groups, filter to them, and return a single number when one value is requested.
label is a short phrase that says exactly what result contains, including units.

Columns:
project, issue_type, priority, priority_group, status, resolution, outcome_group (text)
resolution_days, open_age_days, component_count, priority_order, created_year (numbers)
is_resolved, instant_resolution, bulk_closed, valid_for_duration, bad_dates (true or false)
created, resolved (dates)
key, summary (text)
resolution_days is only meaningful where valid_for_duration is true, so filter on it for any resolution time calculation.

Allowed values:
{values}

Examples:
Q: What percentage of Kafka issues created in 2024 were resolved?
{"label":"Share of Kafka issues created in 2024 that are resolved (%)","code":"d = df[(df.project == 'KAFKA') & (df.created_year == 2024)]\\nresult = round(d.is_resolved.mean() * 100, 2)"}
Q: Resolved share per project for issues created in 2024, in percent
{"label":"Share of 2024 issues that are resolved, by project (%)","code":"d = df[df.created_year == 2024]\\nresult = (d.groupby('project').is_resolved.mean() * 100).round(2).rename('resolved_pct').reset_index()"}
Q: Year-over-year growth of Kafka issues created
{"label":"Year-over-year change in Kafka issues created (%)","code":"s = df[df.project == 'KAFKA'].groupby('created_year').size()\\nresult = (s.pct_change() * 100).round(2).rename('growth_pct').reset_index()"}
Q: By what percentage did the number of Hadoop issues created change from 2019 to 2020?
{"label":"Change in Hadoop issues created from 2019 to 2020 (%)","code":"s = df[df.project == 'HADOOP'].groupby('created_year').size()\\nresult = round((s[2020] / s[2019] - 1) * 100, 2)"}
"""


def number(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return "n/a" if value is None else str(value).replace("|", "/")


def table(columns, rows, total):
    plain = {i for i, c in enumerate(columns) if "year" in c.lower()}
    lines = ["| " + " | ".join(columns) + " |", "|" + " --- |" * len(columns)]
    for row in rows:
        cells = [str(v) if i in plain and v is not None else number(v) for i, v in enumerate(row)]
        lines.append("| " + " | ".join(cells) + " |")
    if total > len(rows):
        lines += ["", f"Showing the first {len(rows)} of {total:,} rows."]
    return "\n".join(lines)


def render(label, out):
    if out["kind"] == "table":
        return f"{label}:\n\n" + table(out["columns"], out["rows"], out["total"])
    return f"{label}: **{number(out['value'])}**"


class AnalysisAgent(Agent):
    name = "analysis"
    description = (
        "Calculations that combine or transform numbers: percentages, shares, ratios, differences, "
        "growth rates, year-over-year change, correlations, cumulative or rolling values, or any other "
        "maths on the ticket fields."
    )

    def run(self, question, context):
        system = SYSTEM.replace("{values}", value_lines(context.store))
        messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
        error = None
        for attempt in range(2):
            raw, _ = chat_json(messages, max_tokens=700)
            if not isinstance(raw, dict):
                raw = {}
            code = raw.get("code")
            label = str(raw.get("label") or "Result")
            try:
                if not isinstance(code, str):
                    raise ValueError("the model returned no code")
                out = sandbox.run(code)
            except ValueError as e:
                error = e
                messages += [
                    {"role": "assistant", "content": json.dumps(raw)},
                    {"role": "user", "content": f"That failed: {e}. Fix the code and reply with the JSON object again."},
                ]
                continue
            return result(self, render(label, out), plan={"label": label, "code": code}, data=out)
        raise ValueError(f"the calculation failed: {error}")