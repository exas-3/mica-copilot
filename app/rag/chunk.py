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
# Enumerated points in EU legal text — "(1)", "(12)", "(a)", "(ii)", or "1.", "2." at an
# item boundary. Used to break a paragraph-less blob (e.g. the Article 3 definitions list)
# so each defined term becomes retrievable instead of being diluted in one mega-chunk.
_ENUM_SPLIT = re.compile(r"(?<=\S)\s+(?=\((?:\d{1,3}|[a-z]{1,3})\)\s)|(?<=\S)\s+(?=\d{1,3}\.\s)")


@dataclass
class Chunk:
    source: str
    article_ref: str
    title: str
    chunk_text: str
    source_url: str
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)


def _hard_wrap(text: str, limit: int) -> list[str]:
    out: list[str] = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit)
        cut = cut if cut > limit // 2 else limit
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


def _atoms(text: str, limit: int) -> list[str]:
    """Sub-budget units: split on paragraphs, then on enumerated items, then hard-wrap."""
    atoms: list[str] = []
    for para in _PARA_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= limit:
            atoms.append(para)
            continue
        for piece in _ENUM_SPLIT.split(para):
            piece = piece.strip()
            if piece:
                atoms.extend(_hard_wrap(piece, limit) if len(piece) > limit else [piece])
    return atoms


def chunk_record(record: dict) -> list[Chunk]:
    """Turn one corpus record into one or more retrievable chunks, each ≤ ~_MAX_CHARS."""
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

    # Pack sub-budget atoms greedily, never exceeding the budget (and never leaving a
    # single over-budget mega-chunk, even when the source has no blank-line breaks).
    parts: list[str] = []
    buf = ""
    for atom in _atoms(text, _MAX_CHARS):
        if buf and len(buf) + len(atom) + 2 > _MAX_CHARS:
            parts.append(buf)
            buf = atom
        else:
            buf = f"{buf}\n\n{atom}" if buf else atom
    if buf:
        parts.append(buf)

    return [Chunk(chunk_text=p, chunk_index=i, **base) for i, p in enumerate(parts)]
