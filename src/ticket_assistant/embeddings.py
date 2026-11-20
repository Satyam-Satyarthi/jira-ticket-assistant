import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from ticket_assistant.config import CHUNKS, EMBED_MODEL, INDEX_DIR

SHARD = 20000
BATCH = 64


def load_model():
    model = SentenceTransformer(EMBED_MODEL)
    model.max_seq_length = 384
    return model


def encode(model, texts):
    vectors = model.encode(
        texts,
        batch_size=BATCH,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vectors.astype(np.float32)


def main():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    chunks = pd.read_json(CHUNKS, lines=True)
    texts = (chunks["title"] + "\n" + chunks["text"]).tolist()
    model = load_model()
    for start in tqdm(range(0, len(texts), SHARD), desc="Embedding", unit="shard"):
        path = INDEX_DIR / f"shard_{start // SHARD:04d}.npy"
        if not path.exists():
            np.save(path, encode(model, texts[start:start + SHARD]))
    shards = sorted(INDEX_DIR.glob("shard_*.npy"))
    np.save(INDEX_DIR / "embeddings.npy", np.vstack([np.load(p) for p in shards]))


if __name__ == "__main__":
    main()