import json

import requests

from ticket_assistant.config import LLM_MODEL, OLLAMA_URL


def chat(messages, json_mode=False, max_tokens=512):
    body = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_ctx": 4096, "num_predict": max_tokens},
    }
    if json_mode:
        body["format"] = "json"
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=600)
    r.raise_for_status()
    data = r.json()
    return data["message"]["content"], data


def chat_json(messages, max_tokens=512):
    text, data = chat(messages, json_mode=True, max_tokens=max_tokens)
    return json.loads(text), data