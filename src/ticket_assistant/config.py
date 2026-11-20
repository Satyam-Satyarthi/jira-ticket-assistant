from pathlib import Path

DATA = Path("data")
RAW_TEXT = DATA / "raw" / "tickets_text.jsonl"
ISSUES_CSV = DATA / "raw" / "issues_clean.csv"
CHUNKS = DATA / "processed" / "chunks.jsonl"
INDEX_DIR = DATA / "processed" / "index"
DUCKDB_PATH = DATA / "processed" / "issues.duckdb"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
COLLECTION = "jira_chunks"
QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL = "qwen2.5:7b-instruct"
