"""Extract plain text from a fetched document (PDF or HTML).

Used by the document-corpus ingester: ESMA/EBA links are sometimes direct PDFs and
sometimes HTML landing pages (Q&A indexes), so we sniff the content and handle both.
"""
from __future__ import annotations

import io
import re

_TAG = re.compile(r"<[^>]+>")


def extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    parts: list[str] = []
    reader = PdfReader(io.BytesIO(data))
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(parts)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_html_text(data: bytes) -> str:
    try:
        import trafilatura

        out = trafilatura.extract(data.decode("utf-8", "replace"),
                                  include_comments=False, include_tables=True, favor_recall=True)
        if out:
            return out.strip()
    except Exception:
        pass
    html = data.decode("utf-8", "replace")
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)</p>|</div>|<br\s*/?>", "\n", html)
    text = _TAG.sub(" ", html)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


def extract_text(data: bytes, content_type: str = "", url: str = "") -> str:
    is_pdf = data[:5] == b"%PDF-" or "pdf" in (content_type or "").lower() or url.lower().endswith(".pdf")
    return extract_pdf_text(data) if is_pdf else extract_html_text(data)
