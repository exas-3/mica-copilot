"""Article-aware chunking.

The corpus is already organised one record per MiCA provision (article / paragraph),
which is the natural retrieval unit for legal RAG — citations map 1:1 to a provision.
Long articles are split on paragraph boundaries with a soft character budget so no
single chunk blows past the embedding model's sweet spot, while short articles stay
whole. Every produced chunk inherits the parent provision's article_ref/title/url so
a retrieved fragment is always attributable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_MAX_CHARS = 1800
_PARA_SPLIT = re.compile(r"\n\s*\n")


@dataclass
class Chunk:
    source: str
    article_ref: str
    title: str
    chunk_text: str
    source_url: str
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)


def chunk_record(record: dict) -> list[Chunk]:
    """Turn one corpus record into one or more retrievable chunks."""
    text = (record.get("chunk_text") or record.get("text") or "").strip()
    if not text:
        return []

    base = dict(
        source=record.get("source", "mica"),
        article_ref=record.get("article_ref", ""),
        title=record.get("title", ""),
        source_url=record.get("source_url", ""),
        metadata=record.get("metadata", {}) or {},
    )

    if len(text) <= _MAX_CHARS:
        return [Chunk(chunk_text=text, chunk_index=0, **base)]

    # Pack paragraphs greedily up to the char budget, never splitting a paragraph.
    parts: list[str] = []
    buf = ""
    for para in _PARA_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if buf and len(buf) + len(para) + 2 > _MAX_CHARS:
            parts.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        parts.append(buf)

    return [Chunk(chunk_text=p, chunk_index=i, **base) for i, p in enumerate(parts)]
