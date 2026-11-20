import json
import re

from tqdm import tqdm

from ticket_assistant.config import CHUNKS, RAW_TEXT

WORDS = 220
OVERLAP = 40
MIN_COMMENT_WORDS = 5

CODE = re.compile(r"\{(?:code|noformat)[^}]*\}.*?\{(?:code|noformat)\}", re.S)
MENTION = re.compile(r"\[~[^\]]+\]")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LINK = re.compile(r"\[([^\]|]+)\|[^\]]+\]")
MACRO = re.compile(r"\{[a-zA-Z]+(?::[^}]*)?\}")
MARKUP = re.compile(r"[*+^~-]{2,}|^h[1-6]\.\s*|^[*#]+\s+", re.M)
SPACE = re.compile(r"\s+")


def clean(text):
    if not text:
        return ""
    text = CODE.sub(lambda m: m.group(0)[:400], text)
    text = MENTION.sub("@user", text)
    text = EMAIL.sub("<email>", text)
    text = LINK.sub(r"\1", text)
    text = MACRO.sub(" ", text)
    text = MARKUP.sub(" ", text)
    return SPACE.sub(" ", text).strip()


def split(words):
    step = WORDS - OVERLAP
    for i in range(0, len(words), step):
        yield " ".join(words[i:i + WORDS])
        if i + WORDS >= len(words):
            break


def pack(comments):
    group, size = [], 0
    for body in comments:
        n = len(body.split())
        if group and size + n > WORDS:
            yield " ".join(group)
            group, size = [], 0
        group.append(body)
        size += n
    if group:
        yield " ".join(group)


def blocks(ticket, title):
    desc = clean(ticket["description"])
    out = [("description", desc) if desc else ("summary", title)]
    comments = [clean(c) for c in ticket["comments"]]
    comments = [c for c in comments if len(c.split()) >= MIN_COMMENT_WORDS]
    out.extend(("comment", group) for group in pack(comments))
    return out


def main():
    CHUNKS.parent.mkdir(parents=True, exist_ok=True)
    with RAW_TEXT.open(encoding="utf-8") as src, CHUNKS.open("w", encoding="utf-8", newline="\n") as out:
        for line in tqdm(src, desc="Chunking", unit="ticket"):
            ticket = json.loads(line)
            key = ticket["key"]
            title = clean(ticket["summary"])
            n = 0
            for source, body in blocks(ticket, title):
                for piece in split(body.split()):
                    record = {
                        "chunk_id": f"{key}#{n}",
                        "key": key,
                        "project": key.split("-")[0],
                        "source": source,
                        "title": title,
                        "text": piece,
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    n += 1


if __name__ == "__main__":
    main()