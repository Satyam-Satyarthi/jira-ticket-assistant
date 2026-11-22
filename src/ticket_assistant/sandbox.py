import ast
import json
import os
import re
import subprocess
import sys

from ticket_assistant.config import DUCKDB_PATH

SAFE_BUILTINS = {
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "float", "int", "len",
    "list", "max", "min", "pow", "range", "reversed", "round", "set", "sorted", "str",
    "sum", "tuple", "zip",
}
ALLOWED_NAMES = SAFE_BUILTINS | {"df", "pd", "np", "math"}
BLOCKED_ATTRS = {
    "eval", "query", "pipe", "system", "popen", "open", "format", "format_map", "style", "plot",
    "load", "save", "savetxt", "loadtxt", "genfromtxt", "fromfile", "tofile", "memmap",
    "io", "compat", "util", "testing", "api", "core", "lib", "ctypeslib", "f2py", "show_versions",
}
BLOCKED_PATTERN = re.compile(r"^(read_.*|to_(csv|pickle|sql|excel|parquet|json|feather|hdf|clipboard|html|latex|stata|xml|orc|gbq))$")
FORBIDDEN_NODES = (
    ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef,
    ast.Global, ast.Nonlocal, ast.Await, ast.Yield, ast.YieldFrom, ast.JoinedStr, ast.With,
)

RUNNER = """
import faulthandler
faulthandler.dump_traceback_later(15, exit=True)
import builtins
import json
import math
import sys

import duckdb
import numpy as np
import pandas as pd

db, names = sys.argv[1], sys.argv[2].split(",")
code = sys.stdin.read()
df = duckdb.connect(db, read_only=True).execute("SELECT * FROM issues").df()
scope = {
    "__builtins__": {n: getattr(builtins, n) for n in names},
    "df": df,
    "pd": pd,
    "np": np,
    "math": math,
}
exec(compile(code, "analysis", "exec"), scope)
value = scope.get("result")
if isinstance(value, pd.Series):
    value = value.reset_index()
if isinstance(value, pd.DataFrame):
    head = value.head(50)
    out = {
        "kind": "table",
        "columns": [str(c) for c in head.columns],
        "rows": json.loads(head.to_json(orient="values", date_format="iso")),
        "total": len(value),
    }
elif isinstance(value, str):
    out = {"kind": "text", "value": value}
elif isinstance(value, (bool, int, float, np.integer, np.floating, np.bool_)):
    value = value.item() if hasattr(value, "item") else value
    if isinstance(value, float) and math.isnan(value):
        value = None
    out = {"kind": "scalar", "value": value}
else:
    raise TypeError("result must be a number, text or table")
print(json.dumps(out))
"""


def check(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"the code is not valid Python ({e.msg})")
    local = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            local.add(node.id)
        if isinstance(node, ast.arg):
            local.add(node.arg)
    if "result" not in local:
        raise ValueError("the code must assign its answer to result")
    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            raise ValueError(f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr in BLOCKED_ATTRS or BLOCKED_PATTERN.match(node.attr):
                raise ValueError(f"attribute {node.attr!r} is not allowed")
        if isinstance(node, ast.Name) and node.id not in ALLOWED_NAMES and node.id not in local:
            raise ValueError(f"name {node.id!r} is not allowed")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
            raise ValueError("double underscores are not allowed")


def run(code, timeout=20):
    check(code)
    env = {k: os.environ[k] for k in ("SYSTEMROOT", "PATH", "TEMP", "TMP") if k in os.environ}
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", RUNNER, str(DUCKDB_PATH.resolve()), ",".join(sorted(SAFE_BUILTINS))],
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("the calculation took too long")
    if proc.returncode != 0:
        if "Timeout (" in proc.stderr:
            raise RuntimeError("the calculation took too long")
        lines = proc.stderr.strip().splitlines()
        raise ValueError(lines[-1] if lines else "the calculation failed")
    return json.loads(proc.stdout.strip().splitlines()[-1])