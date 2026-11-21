from ticket_assistant.agents.base import Agent, result
from ticket_assistant.llm import chat_json
from ticket_assistant.planning import FILTER_RULES, clean_filters, value_lines
from ticket_assistant.structured_store import LIST_COLUMNS, SORTABLE

SYSTEM = """You turn a question that asks for a list of Apache Jira tickets into a JSON query plan. Reply with one JSON object.

Keys: columns, filters, order_by, order, limit.
columns is a list chosen from: {columns}. Always include key and summary.
order_by is null or one of: {sortable}.
order is "asc" or "desc". Oldest first means created asc. Newest first means created desc.
limit is the number of tickets asked for. Use 10 if none is given. The maximum is 50.
{filter_rules}

Allowed values:
{values}

Examples:
Q: List the 10 oldest unresolved Kafka bugs
{"columns":["key","summary","created"],"filters":[{"column":"project","op":"=","value":"KAFKA"},{"column":"issue_type","op":"=","value":"Bug"},{"column":"is_resolved","op":"=","value":false}],"order_by":"created","order":"asc","limit":10}
Q: Show the five Hadoop issues that took longest to resolve
{"columns":["key","summary","resolution_days"],"filters":[{"column":"project","op":"=","value":"HADOOP"}],"order_by":"resolution_days","order":"desc","limit":5}
"""


def cell(value, width=90):
    if isinstance(value, float):
        value = round(value, 1)
    text = "" if value is None else str(value)
    text = text.replace("|", "/").replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def markdown_table(columns, rows):
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(cell(r[c]) for c in columns) + " |" for r in rows]
    return "\n".join([header, divider, *body])


class TableAgent(Agent):
    name = "table"
    description = (
        "Lists or tables of individual tickets chosen by ticket fields only, not by what the tickets say: "
        "show, list, top N, oldest, newest, longest to resolve. Returns ticket keys with titles."
    )

    def run(self, question, context):
        system = (
            SYSTEM.replace("{columns}", ", ".join(LIST_COLUMNS))
            .replace("{sortable}", ", ".join(SORTABLE))
            .replace("{filter_rules}", FILTER_RULES)
            .replace("{values}", value_lines(context.store))
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
        raw, _ = chat_json(messages, max_tokens=500)
        plan = {
            "columns": raw.get("columns"),
            "filters": clean_filters(raw.get("filters"), context.store),
            "order_by": raw.get("order_by"),
            "order": raw.get("order") or "desc",
            "limit": raw.get("limit") or 10,
        }
        out = context.store.select(plan)
        if not out["rows"]:
            return result(self, "No matching issues.", plan=plan, sql=out["sql"], params=out["params"])
        note = " (valid durations only)" if plan["order_by"] == "resolution_days" else ""
        answer = f"Showing {len(out['rows'])} of {out['total']:,} matching issues{note}:\n\n"
        answer += markdown_table(out["columns"], out["rows"])
        table = {"columns": out["columns"], "rows": out["rows"]}
        return result(self, answer, plan=plan, table=table, sql=out["sql"], params=out["params"])