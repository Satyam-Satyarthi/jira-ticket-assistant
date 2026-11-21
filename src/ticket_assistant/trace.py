import json
import time
import uuid
from contextvars import ContextVar

from ticket_assistant.config import LOG_PATH

current = ContextVar("trace", default=None)


def start(question, session_id=None):
    trace = {
        "trace_id": uuid.uuid4().hex[:12],
        "session_id": session_id,
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "question": question,
        "agent": None,
        "llm_calls": [],
        "started": time.time(),
    }
    current.set(trace)
    return trace


def record_llm(meta):
    trace = current.get()
    if trace is not None:
        trace["llm_calls"].append(meta)


def finish(trace, **fields):
    trace.update(fields)
    trace["latency"] = round(time.time() - trace.pop("started"), 2)
    trace["prompt_tokens"] = sum(c.get("prompt_tokens") or 0 for c in trace["llm_calls"])
    trace["completion_tokens"] = sum(c.get("completion_tokens") or 0 for c in trace["llm_calls"])
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")
    current.set(None)
    return trace