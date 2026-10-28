import os

from pymilvus import DataType, MilvusClient

COLLECTION = "lecture_segments"
MAX_CHARS = 60000
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# The embedding model keeps only the first 128 tokens. Stay under that, with a
# short overlap so a fact on a boundary still appears in both neighboring pieces.
CHUNK_TOKENS = 110
OVERLAP_TOKENS = 20
SEARCH_LIMIT = 64
SEPARATORS = ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "；", "; ", "，", ", ", " ", "")

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


def search(document_ids: list[int], query: str, limit: int = SEARCH_LIMIT) -> list[dict]:
    ids = [int(item) for item in document_ids]
    if not ids:
        return []
    client = _client()
    if not client.has_collection(COLLECTION):
        return []
    client.load_collection(COLLECTION)
    vector = _embed([query])[0]
    listed = ", ".join(str(item) for item in ids)
    found = client.search(
        collection_name=COLLECTION,
        data=[vector],
        filter=f"document_id in [{listed}]",
        limit=limit,
        output_fields=["document_id", "page_number", "chapter", "text"],
        search_params={"metric_type": "COSINE"},
    )
    hits = found[0] if found else []
    rows = []
    allowed = set(ids)
    for hit in hits:
        entity = hit.get("entity") or hit
        document_id = int(entity["document_id"])
        if document_id not in allowed:
            continue
        rows.append(
            {
                "document_id": document_id,
                "page_number": int(entity["page_number"]),
                "chapter": entity.get("chapter") or "",
                "text": entity.get("text") or "",
                "score": float(hit.get("distance", 0)),
            }
        )
    return rows


def delete_segments(document_id: int) -> None:
    _delete_document(_client(), int(document_id))


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
        for index, chunk in enumerate(_chunks(body)):
            pieces.append(
                {
                    "document_id": int(document_id),
                    "page_number": int(page["page_number"]),
                    "chunk_index": index,
                    "chapter": (page.get("chapter") or "Untitled")[:255],
                    "text": chunk[:MAX_CHARS],
                }
            )
    return pieces


def _chunks(text: str) -> list[str]:
    pieces = [part for part in _split(text.strip(), SEPARATORS) if part.strip()]
    packed = _pack(pieces)
    return packed or [text.strip()[:MAX_CHARS]]


def _split(text: str, separators: tuple[str, ...]) -> list[str]:
    if _count(text) <= CHUNK_TOKENS:
        return [text]
    for index, separator in enumerate(separators):
        if separator == "":
            return _windows(text)
        parts = text.split(separator)
        if len(parts) <= 1:
            continue
        glued = [part + separator for part in parts[:-1]]
        if parts[-1]:
            glued.append(parts[-1])
        smaller = separators[index + 1 :]
        out = []
        for part in glued:
            if not part:
                continue
            if _count(part) <= CHUNK_TOKENS:
                out.append(part)
            else:
                out.extend(_split(part, smaller))
        return out
    return _windows(text)


def _pack(pieces: list[str]) -> list[str]:
    chunks = []
    buf: list[str] = []
    buf_tokens = 0
    for piece in pieces:
        tokens = _count(piece)
        if buf and buf_tokens + tokens > CHUNK_TOKENS:
            chunks.append("".join(buf).strip())
            budget = min(OVERLAP_TOKENS, max(0, CHUNK_TOKENS - tokens))
            carry: list[str] = []
            carry_tokens = 0
            for prev in reversed(buf):
                prev_tokens = _count(prev)
                if carry_tokens + prev_tokens > budget:
                    break
                carry.insert(0, prev)
                carry_tokens += prev_tokens
            buf = carry
            buf_tokens = carry_tokens
        buf.append(piece)
        buf_tokens += tokens
    if buf:
        text = "".join(buf).strip()
        if text:
            chunks.append(text)
    return [chunk for chunk in chunks if chunk]


def _windows(text: str) -> list[str]:
    tokenizer = _tokenizer()
    ids = tokenizer.encode(text, add_special_tokens=False).ids
    if not ids:
        return []
    step = max(1, CHUNK_TOKENS - OVERLAP_TOKENS)
    windows = []
    start = 0
    while start < len(ids):
        decoded = tokenizer.decode(ids[start : start + CHUNK_TOKENS]).strip()
        if decoded:
            windows.append(decoded)
        if start + CHUNK_TOKENS >= len(ids):
            break
        start += step
    return windows


def _count(text: str) -> int:
    if not text:
        return 0
    return len(_tokenizer().encode(text, add_special_tokens=False).ids)


def _tokenizer():
    return _embedder().model.tokenizer


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
