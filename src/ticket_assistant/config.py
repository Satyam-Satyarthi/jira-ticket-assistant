import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA = Path("data")
RAW_TEXT = DATA / "raw" / "tickets_text.jsonl"
ISSUES_CSV = DATA / "raw" / "issues_clean.csv"
CHUNKS = DATA / "processed" / "chunks.jsonl"
INDEX_DIR = DATA / "processed" / "index"
DUCKDB_PATH = DATA / "processed" / "issues.duckdb"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
COLLECTION = "jira_chunks"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LLM_PROVIDERS = os.getenv("LLM_PROVIDERS", "groq,gemini").split(",")
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL = "qwen2.5:7b-instruct"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL")
