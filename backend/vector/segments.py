import os

from pymilvus import DataType, MilvusClient

COLLECTION = "lecture_segments"
MAX_CHARS = 60000
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model = None


def sync_pages(document_id: int, pages: list[dict]) -> int:
    pieces = _pieces(document_id, pages)
    client = _client()
    if not pieces:
        _ensure_collection(client, 384)
        _delete_document(client, document_id)
        return 0

    vectors = _embed([piece["text"] for piece in pieces])
    _ensure_collection(client, len(vectors[0]))
    _delete_document(client, document_id)
    rows = []
    for piece, vector in zip(pieces, vectors):
        row = dict(piece)
        row["vector"] = vector
        rows.append(row)
    client.insert(collection_name=COLLECTION, data=rows)
    return len(rows)


def segments_for(document_id: int) -> list[dict]:
    client = _client()
    if not client.has_collection(COLLECTION):
        return []
    rows = client.query(
        collection_name=COLLECTION,
        filter=f"document_id == {int(document_id)}",
        output_fields=["document_id", "page_number", "chunk_index", "chapter", "text"],
        limit=10000,
    )
    return sorted(rows, key=lambda row: (row["page_number"], row["chunk_index"]))


def _pieces(document_id: int, pages: list[dict]) -> list[dict]:
    pieces = []
    for page in pages:
        body = page.get("body") or ""
        if not page.get("usable") or not body.strip():
            continue
        chunks = [body[start : start + MAX_CHARS] for start in range(0, len(body), MAX_CHARS)]
        for index, chunk in enumerate(chunks):
            pieces.append(
                {
                    "document_id": int(document_id),
                    "page_number": int(page["page_number"]),
                    "chunk_index": index,
                    "chapter": (page.get("chapter") or "未标注")[:255],
                    "text": chunk,
                }
            )
    return pieces


def _embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for vector in _embedder().embed(texts):
        vectors.append([float(value) for value in vector])
    return vectors


def _embedder():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(MODEL_NAME)
    return _model


def _client() -> MilvusClient:
    return MilvusClient(uri=os.environ.get("MILVUS_URI", "http://127.0.0.1:19530"))


def _ensure_collection(client: MilvusClient, dimension: int) -> None:
    if client.has_collection(COLLECTION):
        return
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
    schema.add_field("document_id", DataType.INT64)
    schema.add_field("page_number", DataType.INT64)
    schema.add_field("chunk_index", DataType.INT64)
    schema.add_field("chapter", DataType.VARCHAR, max_length=255)
    schema.add_field("text", DataType.VARCHAR, max_length=65535)
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(
        collection_name=COLLECTION,
        schema=schema,
        index_params=index_params,
    )


def _delete_document(client: MilvusClient, document_id: int) -> None:
    if not client.has_collection(COLLECTION):
        return
    rows = client.query(
        collection_name=COLLECTION,
        filter=f"document_id == {int(document_id)}",
        output_fields=["id"],
        limit=10000,
    )
    ids = [row["id"] for row in rows]
    if ids:
        client.delete(collection_name=COLLECTION, ids=ids)
