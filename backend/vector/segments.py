import os
import re

from pymilvus import (
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)

COLLECTION = "lecture_segments"
MAX_CHARS = 60000
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# The embedding model keeps only the first 128 tokens. A structural piece that
# fits stays whole. A longer piece is split into fixed windows, with a short
# overlap so a fact on a boundary still appears in both neighboring pieces.
CHUNK_TOKENS = 110
OVERLAP_TOKENS = 20
SEARCH_LIMIT = 30
SEPARATORS = ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "；", "; ", "，", ", ", " ", "")
_HEADING = re.compile(r"^#{1,6}\s+\S")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
_SENTENCE_END = re.compile(r"[.!?;](?=\s|$)|[。！？；]")
_CLOSED_LINE = re.compile(r"[.!?。！？;；:：]['\"”’)\]]*$")
# A sentence broken by a page break is indexed once more as a bridge piece on
# the earlier page. Each side is capped so the whole sentence fits the
# embedding model.
BRIDGE_HEAD_TOKENS = 60
BRIDGE_TAIL_TOKENS = 45

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
    client.flush(COLLECTION)
    return len(rows)


def has_segments(document_id: int) -> bool:
    client = _client()
    if not _usable_collection(client):
        return False
    rows = client.query(
        collection_name=COLLECTION,
        filter=f"document_id == {int(document_id)}",
        output_fields=["document_id"],
        limit=1,
    )
    return bool(rows)


def search(document_ids: list[int], query: str, limit: int = SEARCH_LIMIT) -> list[dict]:
    ids = [int(item) for item in document_ids]
    text = query.strip()
    if not ids or not text:
        return []
    client = _client()
    if not _usable_collection(client):
        return []
    client.load_collection(COLLECTION)
    vector = _embed([text])[0]
    expr = f"document_id in [{', '.join(str(item) for item in ids)}]"
    dense = AnnSearchRequest(
        data=[vector],
        anns_field="vector",
        param={"metric_type": "COSINE"},
        limit=limit,
        expr=expr,
    )
    sparse = AnnSearchRequest(
        data=[text],
        anns_field="sparse",
        param={"metric_type": "BM25"},
        limit=limit,
        expr=expr,
    )
    found = client.hybrid_search(
        collection_name=COLLECTION,
        reqs=[dense, sparse],
        ranker=RRFRanker(k=60),
        limit=limit,
        output_fields=["document_id", "page_number", "chapter", "text"],
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
    if not _usable_collection(client):
        return []
    rows = client.query(
        collection_name=COLLECTION,
        filter=f"document_id == {int(document_id)}",
        output_fields=["document_id", "page_number", "chunk_index", "chapter", "text"],
        limit=10000,
    )
    return sorted(rows, key=lambda row: (row["page_number"], row["chunk_index"]))


def chunk_text(text: str) -> list[str]:
    chunks = []
    for heading, body in _structure_blocks(text):
        chunks.extend(_emit_block(heading, body))
    return [chunk[:MAX_CHARS] for chunk in chunks if chunk.strip()]


def bridge_text(body: str, next_body: str) -> str | None:
    head = _open_sentence(body)
    if head is None:
        return None
    tail = _continued_sentence(next_body)
    if tail is None:
        return None
    head = _last_tokens(head, BRIDGE_HEAD_TOKENS)
    tail = _first_tokens(tail, BRIDGE_TAIL_TOKENS)
    if not head or not tail:
        return None
    return f"{head} {tail}"


def _open_sentence(body: str) -> str | None:
    lines = [line for line in body.strip().split("\n") if line.strip()]
    if not lines:
        return None
    last = lines[-1].strip()
    if _HEADING.match(last) or last.startswith("|") or _CLOSED_LINE.search(last):
        return None
    paragraph = []
    for line in reversed(lines):
        stripped = line.strip()
        if _HEADING.match(stripped) or stripped.startswith("|"):
            break
        paragraph.insert(0, stripped)
    text = " ".join(paragraph)
    ends = list(_SENTENCE_END.finditer(text))
    head = text[ends[-1].end():] if ends else text
    head = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", head).strip()
    return head or None


def _continued_sentence(next_body: str) -> str | None:
    lines = []
    for line in next_body.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            break
        lines.append(stripped)
    if not lines:
        return None
    first = lines[0]
    if _HEADING.match(first) or first.startswith("|") or _LIST_ITEM.match(first):
        return None
    text = " ".join(lines)
    end = _SENTENCE_END.search(text)
    tail = text[: end.end()] if end else text
    return tail.strip() or None


def _first_tokens(text: str, limit: int) -> str:
    tokenizer = _tokenizer()
    ids = tokenizer.encode(text, add_special_tokens=False).ids
    if len(ids) <= limit:
        return text.strip()
    return tokenizer.decode(ids[:limit]).strip()


def _last_tokens(text: str, limit: int) -> str:
    tokenizer = _tokenizer()
    ids = tokenizer.encode(text, add_special_tokens=False).ids
    if len(ids) <= limit:
        return text.strip()
    return tokenizer.decode(ids[-limit:]).strip()


def _pieces(document_id: int, pages: list[dict]) -> list[dict]:
    pieces = []
    by_number = {
        int(page["page_number"]): str(page.get("body") or "")
        for page in pages
        if page.get("usable")
    }
    for page in pages:
        body = page.get("body") or ""
        if not page.get("usable") or not str(body).strip():
            continue
        chunks = chunk_text(str(body))
        next_body = by_number.get(int(page["page_number"]) + 1)
        if next_body:
            bridge = bridge_text(str(body), next_body)
            if bridge:
                chunks.append(bridge)
        for index, chunk in enumerate(chunks):
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


def _structure_blocks(text: str) -> list[tuple[str, str]]:
    heading = ""
    heading_has_body = False
    blocks: list[tuple[str, str]] = []
    buffer: list[str] = []
    mode = ""

    def flush() -> None:
        nonlocal buffer, mode, heading_has_body
        body = "\n".join(buffer).strip()
        buffer = []
        mode = ""
        if not body:
            return
        heading_has_body = True
        blocks.append((heading, body))

    for line in text.replace("\r\n", "\n").split("\n"):
        if _HEADING.match(line.strip()):
            flush()
            if heading and not heading_has_body:
                blocks.append(("", heading))
            heading = line.strip()
            heading_has_body = False
            continue
        if not line.strip():
            flush()
            continue
        kind = _line_kind(line)
        if mode and mode != kind:
            flush()
        mode = kind
        buffer.append(line)
    flush()
    if heading and not heading_has_body:
        blocks.append(("", heading))
    return blocks


def _line_kind(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("|") or _is_table_rule(stripped):
        return "table"
    if _LIST_ITEM.match(stripped):
        return "list"
    return "paragraph"


def _is_table_rule(line: str) -> bool:
    compact = line.replace(" ", "")
    return bool(compact) and set(compact) <= set("|-:") and "-" in compact and "|" in compact


def _emit_block(heading: str, body: str) -> list[str]:
    body = body.strip()
    if not body:
        return []
    prefix = heading.strip()
    if prefix and (body == prefix or body.startswith(prefix + "\n")):
        prefix = ""
    combined = f"{prefix}\n{body}".strip() if prefix else body
    if _count(combined) <= CHUNK_TOKENS:
        return [combined]

    budget = CHUNK_TOKENS
    if prefix and _count(prefix) < CHUNK_TOKENS - 20:
        budget = CHUNK_TOKENS - _count(prefix) - 1
    else:
        prefix = ""
    pieces = _fixed_chunks(body if prefix else combined, budget)
    emitted = []
    for piece in pieces:
        text = f"{prefix}\n{piece}".strip() if prefix else piece.strip()
        if text:
            emitted.append(text)
    return emitted


def _fixed_chunks(text: str, limit: int) -> list[str]:
    pieces = [part for part in _split(text.strip(), SEPARATORS, limit) if part.strip()]
    packed = _pack(pieces, limit)
    return packed or _windows(text, limit)


def _split(text: str, separators: tuple[str, ...], limit: int) -> list[str]:
    if _count(text) <= limit:
        return [text]
    for index, separator in enumerate(separators):
        if separator == "":
            return _windows(text, limit)
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
            if _count(part) <= limit:
                out.append(part)
            else:
                out.extend(_split(part, smaller, limit))
        return out
    return _windows(text, limit)


def _pack(pieces: list[str], limit: int) -> list[str]:
    overlap = min(OVERLAP_TOKENS, max(0, limit // 5))
    chunks = []
    buf: list[str] = []
    buf_tokens = 0
    for piece in pieces:
        tokens = _count(piece)
        if buf and buf_tokens + tokens > limit:
            chunks.append("".join(buf).strip())
            budget = min(overlap, max(0, limit - tokens))
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


def _windows(text: str, limit: int) -> list[str]:
    tokenizer = _tokenizer()
    ids = tokenizer.encode(text, add_special_tokens=False).ids
    if not ids:
        return []
    overlap = min(OVERLAP_TOKENS, max(0, limit // 5))
    step = max(1, limit - overlap)
    windows = []
    start = 0
    while start < len(ids):
        decoded = tokenizer.decode(ids[start : start + limit]).strip()
        if decoded:
            windows.append(decoded)
        if start + limit >= len(ids):
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


def _usable_collection(client: MilvusClient) -> bool:
    if not client.has_collection(COLLECTION):
        return False
    if _hybrid_ready(client):
        return True
    client.drop_collection(COLLECTION)
    return False


def _hybrid_ready(client: MilvusClient) -> bool:
    description = client.describe_collection(COLLECTION)
    names = set()
    for field in description.get("fields") or []:
        if isinstance(field, dict):
            names.add(field.get("name"))
        else:
            names.add(getattr(field, "name", None))
    return "sparse" in names and "vector" in names


def _ensure_collection(client: MilvusClient, dimension: int) -> None:
    if client.has_collection(COLLECTION):
        if _hybrid_ready(client):
            return
        client.drop_collection(COLLECTION)
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field("document_id", DataType.INT64)
    schema.add_field("page_number", DataType.INT64)
    schema.add_field("chunk_index", DataType.INT64)
    schema.add_field("chapter", DataType.VARCHAR, max_length=255)
    schema.add_field(
        "text",
        DataType.VARCHAR,
        max_length=65535,
        enable_analyzer=True,
        analyzer_params={"type": "standard"},
    )
    schema.add_function(
        Function(
            name="text_bm25",
            input_field_names=["text"],
            output_field_names=["sparse"],
            function_type=FunctionType.BM25,
        )
    )
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
    index_params.add_index(
        field_name="sparse",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
    )
    client.create_collection(
        collection_name=COLLECTION,
        schema=schema,
        index_params=index_params,
    )


def _delete_document(client: MilvusClient, document_id: int) -> None:
    if not client.has_collection(COLLECTION):
        return
    if not _hybrid_ready(client):
        client.drop_collection(COLLECTION)
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
        client.flush(COLLECTION)
