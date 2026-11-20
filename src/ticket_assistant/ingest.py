import json
import time

import pandas as pd
import requests
from tqdm import tqdm

from ticket_assistant.config import ISSUES_CSV, RAW_TEXT

URL = "https://issues.apache.org/jira/rest/api/2/search"
FIELDS = ["summary", "description", "comment"]
BATCH = 100
PAUSE = 1.0
HEADERS = {"User-Agent": "portfolio-project (contact: your-email@example.com)"}


def repair():
    if not RAW_TEXT.exists():
        return
    good = []
    with RAW_TEXT.open(encoding="utf-8") as f:
        for line in f:
            try:
                json.loads(line)
            except json.JSONDecodeError:
                continue
            good.append(line if line.endswith("\n") else line + "\n")
    with RAW_TEXT.open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(good)


def done_keys():
    if not RAW_TEXT.exists():
        return set()
    with RAW_TEXT.open(encoding="utf-8") as f:
        return {json.loads(line)["key"] for line in f}


def fetch(session, keys):
    body = {
        "jql": f"key in ({','.join(keys)})",
        "fields": FIELDS,
        "maxResults": len(keys),
    }
    for attempt in range(5):
        r = session.post(URL, json=body, timeout=60)
        if r.status_code == 200:
            return r.json()["issues"]
        time.sleep(5 * 2 ** attempt)
    r.raise_for_status()


def flatten(issue):
    f = issue["fields"]
    comments = [c["body"] for c in (f.get("comment") or {}).get("comments", [])]
    return {
        "key": issue["key"],
        "summary": f.get("summary"),
        "description": f.get("description"),
        "comments": comments,
    }


def main():
    repair()
    keys = pd.read_csv(ISSUES_CSV, usecols=["key"])["key"].tolist()
    todo = [k for k in keys if k not in done_keys()]
    session = requests.Session()
    session.headers.update(HEADERS)
    with RAW_TEXT.open("a", encoding="utf-8", newline="\n") as f:
        for i in tqdm(range(0, len(todo), BATCH), desc="Fetching", unit="batch"):
            for issue in fetch(session, todo[i:i + BATCH]):
                f.write(json.dumps(flatten(issue), ensure_ascii=False) + "\n")
            f.flush()
            time.sleep(PAUSE)
    print(f"{len(done_keys())} of {len(keys)} tickets saved")


if __name__ == "__main__":
    main()