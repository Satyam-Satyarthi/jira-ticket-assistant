import duckdb

from ticket_assistant.config import DUCKDB_PATH, ISSUES_CSV, RAW_TEXT

CATEGORICAL = ["project", "issue_type", "priority", "priority_group", "status", "resolution", "outcome_group"]
NUMERIC = ["resolution_days", "open_age_days", "component_count", "priority_order", "created_year"]
BOOLEAN = ["is_resolved", "instant_resolution", "bulk_closed", "valid_for_duration", "bad_dates"]
DATES = ["created", "resolved"]
GROUPABLE = CATEGORICAL + ["created_year"]
METRICS = {"count", "avg", "median", "min", "max", "sum"}
OPS = {"=", "!=", ">", ">=", "<", "<=", "in"}
EXACT_ONLY = {"=", "!=", "in"}
LIST_COLUMNS = [
    "key", "summary", "project", "issue_type", "priority", "status", "resolution",
    "created", "resolved", "resolution_days", "open_age_days", "component_count",
]
SORTABLE = ["created", "resolved", "resolution_days", "open_age_days", "component_count", "priority_order"]


def build():
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute(
        "CREATE OR REPLACE TABLE issues AS "
        "SELECT * REPLACE (CAST(created AS DATE) AS created, CAST(resolved AS DATE) AS resolved), "
        "year(created) AS created_year "
        f"FROM read_csv_auto('{ISSUES_CSV.as_posix()}', header=true)"
    )
    con.execute(
        "CREATE TABLE issues_titled AS SELECT i.*, t.summary FROM issues i "
        "LEFT JOIN (SELECT key, summary FROM read_json("
        f"'{RAW_TEXT.as_posix()}', format='newline_delimited', columns={{key: 'VARCHAR', summary: 'VARCHAR'}})) t "
        "USING (key)"
    )
    con.execute("DROP TABLE issues")
    con.execute("ALTER TABLE issues_titled RENAME TO issues")
    con.close()


class Store:
    def __init__(self):
        self.con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        self.values = {}
        for column in CATEGORICAL:
            rows = self.con.execute(
                f"SELECT DISTINCT {column} FROM issues WHERE {column} IS NOT NULL"
            ).fetchall()
            self.values[column] = {str(r[0]).lower(): str(r[0]) for r in rows}

    def _clean(self, column, value):
        if column in CATEGORICAL:
            found = self.values[column].get(str(value).lower())
            if found is None:
                raise ValueError(f"unknown value {value!r} for {column}")
            return found
        if column in BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError(f"{column} needs true or false")
            return value
        if column in DATES:
            return str(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{column} needs a number")
        return value

    def _where(self, filters):
        parts, params = [], []
        for f in filters:
            column, op = f["column"], f.get("op", "=")
            if column not in CATEGORICAL + NUMERIC + BOOLEAN + DATES:
                raise ValueError(f"unknown column {column!r}")
            if op not in OPS:
                raise ValueError(f"unsupported operator {op!r}")
            if column in CATEGORICAL + BOOLEAN and op not in EXACT_ONLY:
                raise ValueError(f"{op} is not valid for {column}")
            marker = "CAST(? AS DATE)" if column in DATES else "?"
            if op == "in":
                values = [self._clean(column, v) for v in f["value"]]
                if not values:
                    raise ValueError("empty list for in")
                parts.append(f"{column} IN ({', '.join(marker for _ in values)})")
                params.extend(values)
            else:
                parts.append(f"{column} {op} {marker}")
                params.append(self._clean(column, f["value"]))
        return parts, params

    def query(self, spec):
        metric = spec.get("metric", "count")
        if metric not in METRICS:
            raise ValueError(f"unsupported metric {metric!r}")
        column = spec.get("column")
        if metric == "count":
            expr = "COUNT(*)"
        else:
            if column not in NUMERIC:
                raise ValueError(f"{metric} needs a numeric column")
            expr = f"ROUND({metric.upper()}({column}), 2)"
        filters = list(spec.get("filters", []))
        if column == "resolution_days" and not any(f["column"] == "valid_for_duration" for f in filters):
            filters.append({"column": "valid_for_duration", "op": "=", "value": True})
        group = spec.get("group_by")
        if group and group not in GROUPABLE:
            raise ValueError(f"cannot group by {group!r}")
        limit = min(int(spec.get("limit", 20)), 50)
        parts, params = self._where(filters)
        select = f"{group}, {expr} AS value" if group else f"{expr} AS value"
        sql = f"SELECT {select} FROM issues"
        if parts:
            sql += " WHERE " + " AND ".join(parts)
        if group:
            order = group if group == "created_year" else "value DESC"
            sql += f" GROUP BY {group} ORDER BY {order} LIMIT {limit}"
        cur = self.con.execute(sql, params)
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
        return {"sql": sql, "params": params, "rows": rows}

    def select(self, spec):
        columns = spec.get("columns") or ["key", "summary", "issue_type", "status", "created"]
        for column in columns:
            if column not in LIST_COLUMNS:
                raise ValueError(f"cannot show column {column!r}")
        order = spec.get("order_by")
        if order and order not in SORTABLE:
            raise ValueError(f"cannot sort by {order!r}")
        direction = "ASC" if str(spec.get("order", "desc")).lower() == "asc" else "DESC"
        try:
            limit = min(max(int(spec.get("limit") or 10), 1), 50)
        except (TypeError, ValueError) as e:
            raise ValueError("limit must be a number") from e
        filters = list(spec.get("filters", []))
        if order == "resolution_days" and not any(f["column"] == "valid_for_duration" for f in filters):
            filters.append({"column": "valid_for_duration", "op": "=", "value": True})
        parts, params = self._where(filters)
        where = " WHERE " + " AND ".join(parts) if parts else ""
        sql = f"SELECT {', '.join(columns)} FROM issues{where}"
        if order:
            sql += f" ORDER BY {order} {direction} NULLS LAST, key"
        sql += f" LIMIT {limit}"
        cur = self.con.execute(sql, params)
        names = [d[0] for d in cur.description]
        rows = [
            {n: (v.isoformat() if hasattr(v, "isoformat") else v) for n, v in zip(names, r)}
            for r in cur.fetchall()
        ]
        total = self.con.execute(f"SELECT COUNT(*) FROM issues{where}", params).fetchone()[0]
        return {"sql": sql, "params": params, "rows": rows, "columns": columns, "total": total}


if __name__ == "__main__":
    build()