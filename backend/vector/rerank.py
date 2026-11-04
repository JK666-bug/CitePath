from fastembed.rerank.cross_encoder import TextCrossEncoder

MODEL_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"
_model = None


def rerank(query: str, hits: list[dict]) -> list[dict]:
    if not hits:
        return []
    scores = list(_encoder().rerank(query, [str(hit.get("text") or "") for hit in hits]))
    ranked = []
    for hit, score in zip(hits, scores):
        row = dict(hit)
        row["score"] = float(score)
        ranked.append(row)
    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked


def _encoder() -> TextCrossEncoder:
    global _model
    if _model is None:
        _model = TextCrossEncoder(model_name=MODEL_NAME)
    return _model
