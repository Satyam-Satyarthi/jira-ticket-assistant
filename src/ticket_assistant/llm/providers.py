import re

import requests

from ticket_assistant.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    HF_MODEL,
    HF_TOKEN,
    LLM_MODEL,
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    NVIDIA_API_KEY,
    NVIDIA_MODEL,
    OLLAMA_URL,
)


class ProviderError(Exception):
    pass


def post(url, timeout=30, **kwargs):
    try:
        r = requests.post(url, timeout=timeout, **kwargs)
    except requests.RequestException as e:
        raise ProviderError(str(e)) from e
    if r.status_code != 200:
        raise ProviderError(f"{r.status_code}: {r.text[:200]}")
    return r.json()


def require_text(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    if not text.strip():
        raise ProviderError("empty response")
    return text.strip()


class Groq:
    name = "groq"

    def __init__(self):
        self.model = GROQ_MODEL

    def ready(self):
        return bool(GROQ_API_KEY)

    def complete(self, messages, json_mode, max_tokens):
        try:
            return self.call(messages, json_mode, max_tokens)
        except ProviderError as e:
            if json_mode and "validate JSON" in str(e):
                return self.call(messages, False, max_tokens)
            raise

    def call(self, messages, json_mode, max_tokens):
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        data = post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json=body,
        )
        usage = data.get("usage", {})
        text = require_text(data["choices"][0]["message"].get("content"))
        return text, usage.get("prompt_tokens"), usage.get("completion_tokens")


class Gemini:
    name = "gemini"

    def __init__(self):
        self.model = GEMINI_MODEL

    def ready(self):
        return bool(GEMINI_API_KEY)

    def complete(self, messages, json_mode, max_tokens):
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
            if m["role"] != "system"
        ]
        config = {"temperature": 0, "maxOutputTokens": max_tokens}
        if json_mode:
            config["responseMimeType"] = "application/json"
        body = {"contents": contents, "generationConfig": config}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        data = post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json=body,
        )
        candidates = data.get("candidates") or [{}]
        parts = candidates[0].get("content", {}).get("parts", [])
        text = require_text("".join(p.get("text", "") for p in parts))
        usage = data.get("usageMetadata", {})
        return text, usage.get("promptTokenCount"), usage.get("candidatesTokenCount")


class Ollama:
    name = "ollama"

    def __init__(self):
        self.model = LLM_MODEL

    def ready(self):
        return True

    def complete(self, messages, json_mode, max_tokens):
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": max_tokens},
        }
        if json_mode:
            body["format"] = "json"
        data = post(f"{OLLAMA_URL}/api/chat", timeout=600, json=body)
        text = require_text(data["message"]["content"])
        return text, data.get("prompt_eval_count"), data.get("eval_count")


class Compat:
    def __init__(self, name, url, key, model, json_mode=True):
        self.name = name
        self.url = url
        self.key = key
        self.model = model
        self.json_mode = json_mode

    def ready(self):
        return bool(self.key and self.model)

    def complete(self, messages, json_mode, max_tokens):
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
        if json_mode and self.json_mode:
            body["response_format"] = {"type": "json_object"}
        data = post(self.url, headers={"Authorization": f"Bearer {self.key}"}, json=body)
        usage = data.get("usage", {})
        text = require_text(data["choices"][0]["message"].get("content"))
        return text, usage.get("prompt_tokens"), usage.get("completion_tokens")


def mistral():
    return Compat("mistral", "https://api.mistral.ai/v1/chat/completions", MISTRAL_API_KEY, MISTRAL_MODEL)


def nvidia():
    return Compat(
        "nvidia", "https://integrate.api.nvidia.com/v1/chat/completions", NVIDIA_API_KEY, NVIDIA_MODEL, json_mode=False
    )


def huggingface():
    return Compat("huggingface", "https://router.huggingface.co/v1/chat/completions", HF_TOKEN, HF_MODEL, json_mode=False)