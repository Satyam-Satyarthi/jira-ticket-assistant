import numpy as np
import pandas as pd
from qdrant_client import QdrantClient, models
from tqdm import tqdm

from ticket_assistant.config import CHUNKS, COLLECTION, INDEX_DIR, ISSUES_CSV, QDRANT_API_KEY, QDRANT_URL

BATCH = 256
DIMENSION = 384
KEYWORD_FIELDS = ["key", "project", "source", "issue_type", "priority_group", "status", "outcome_group"]
META_COLUMNS = ["issue_type", "priority_group", "status", "outcome_group", "is_resolved"]


def load_meta():
    issues = pd.read_csv(ISSUES_CSV, usecols=["key", "created"] + META_COLUMNS)
    issues["created_year"] = pd.to_datetime(issues["created"], errors="coerce").dt.year.astype("Int64")
    issues = issues.drop(columns="created").set_index("key")
    issues = issues.astype(object).where(issues.notna(), None)
    return issues.to_dict("index")


def ensure_collection(client):
    if client.collection_exists(COLLECTION):
        return client.count(COLLECTION, exact=True).count
    client.create_collection(
        COLLECTION,
        vectors_config=models.VectorParams(size=DIMENSION, distance=models.Distance.COSINE, on_disk=True),
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8, quantile=0.99, always_ram=True
            )
        ),
        on_disk_payload=True,
    )
    for field in KEYWORD_FIELDS:
        client.create_payload_index(COLLECTION, field, models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION, "created_year", models.PayloadSchemaType.INTEGER)
    client.create_payload_index(COLLECTION, "is_resolved", models.PayloadSchemaType.BOOL)
    return 0


def main():
    rows = pd.read_json(CHUNKS, lines=True).to_dict("records")
    vectors = np.load(INDEX_DIR / "embeddings.npy")
    meta = load_meta()
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=120)
    start = ensure_collection(client)
    for i in tqdm(range(start, len(rows), BATCH), desc="Uploading", unit="batch"):
        points = []
        for j in range(i, min(i + BATCH, len(rows))):
            payload = {**rows[j], **meta.get(rows[j]["key"], {})}
            points.append(models.PointStruct(id=j, vector=vectors[j].tolist(), payload=payload))
        client.upsert(COLLECTION, points=points, wait=True)


if __name__ == "__main__":
    main()