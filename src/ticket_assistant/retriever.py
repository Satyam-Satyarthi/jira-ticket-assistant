import time
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from ticket_assistant.config import COLLECTION, QDRANT_API_KEY, QDRANT_URL, QUERY_PREFIX
from ticket_assistant.embeddings import load_model

FILTER_FIELDS = {
    "project", "issue_type", "priority_group", "status",
    "outcome_group", "is_resolved", "created_year", "source",
}

SEARCH_PARAMS = models.SearchParams(
    quantization=models.QuantizationSearchParams(rescore=True, oversampling=3.0)
)

def build_filter(filters):
    if not filters:
        return None
    must = []
    for field, value in filters.items():
        if field not in FILTER_FIELDS:
            raise ValueError(f"cannot filter on {field!r}")
        if isinstance(value, list):
            match = models.MatchAny(any=value)
        else:
            match = models.MatchValue(value=value)
        must.append(models.FieldCondition(key=field, match=match))
    return models.Filter(must=must)

def retry(call, tries=3):
    for attempt in range(tries):
        try:
            return call()
        except (ResponseHandlingException, ConnectionError):
            if attempt == tries - 1:
                raise
            time.sleep(2)

class Retriever:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
        self.model = load_model()

    def search(self, query, k=5, filters=None, per_ticket=2):
        vector = self.model.encode(QUERY_PREFIX + query, normalize_embeddings=True)
        result = retry(lambda: self.client.query_points_groups(
            COLLECTION,
            query=vector.tolist(),
            group_by="key",
            limit=k,
            group_size=per_ticket,
            query_filter=build_filter(filters),
            with_payload=True,
            search_params=SEARCH_PARAMS,
        ))
        hits = []
        for group in result.groups:
            for point in group.hits:
                p = point.payload
                hits.append({
                    "chunk_id": p["chunk_id"],
                    "key": p["key"],
                    "project": p["project"],
                    "source": p["source"],
                    "title": p["title"],
                    "text": p["text"],
                    "score": float(point.score),
                })
        return hits