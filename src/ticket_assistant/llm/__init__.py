import json
import time

from ticket_assistant.config import LLM_PROVIDERS
from ticket_assistant.llm.providers import Gemini, Groq, Ollama, ProviderError, huggingface, mistral, nvidia

REGISTRY = {
    "groq": Groq,
    "gemini": Gemini,
    "ollama": Ollama,
    "mistral": mistral,
    "nvidia": nvidia,
    "huggingface": huggingface,
}


def providers():
    chain = [REGISTRY[name.strip()]() for name in LLM_PROVIDERS if name.strip() in REGISTRY]
    return [p for p in chain if p.ready()]


def chat(messages, json_mode=False, max_tokens=512):
    errors = []
    for provider in providers():
        start = time.time()
        try:
            text, prompt_tokens, completion_tokens = provider.complete(messages, json_mode, max_tokens)
        except ProviderError as e:
            errors.append(f"{provider.name}: {e}")
            continue
        meta = {
            "provider": provider.name,
            "model": provider.model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency": round(time.time() - start, 2),
            "fallbacks": errors,
        }
        return text, meta
    raise RuntimeError("no LLM provider answered: " + "; ".join(errors))

def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start:end + 1])

def chat_json(messages, max_tokens=512):
    text, meta = chat(messages, json_mode=True, max_tokens=max_tokens)
    return parse_json(text), meta