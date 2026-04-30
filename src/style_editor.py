"""Deterministic Markdown style pass."""

from __future__ import annotations

import re
from typing import Any


def apply_style(payload: dict[str, Any]) -> dict[str, Any]:
    markdown = _normalize_markdown(str(payload.get("draft_markdown") or ""))
    style = str(payload.get("style") or payload.get("tone") or "warm_blog")
    if not markdown:
        markdown = "# Untitled\n\n아직 작성된 본문이 없습니다."

    if style == "concise":
        markdown = _compact_bullets(markdown)
    elif style == "warm_blog":
        markdown = _add_warm_touch(markdown)

    return {
        "style_status": "ok",
        "applied_style": style,
        "markdown": markdown,
        "word_count": len(re.findall(r"\S+", markdown)),
    }


def _normalize_markdown(markdown: str) -> str:
    lines = [line.rstrip() for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                normalized.append("")
            blank = True
            continue
        normalized.append(line)
        blank = False
    normalized_markdown = "\n".join(normalized).strip()
    return normalized_markdown + "\n" if normalized_markdown else ""


def _compact_bullets(markdown: str) -> str:
    return re.sub(r"(?m)^- ([^\n]{90})[^\n]*$", r"- \1...", markdown)


def _add_warm_touch(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# ") and "기록해 둔 순간들을 차분히 따라가 봅니다." not in markdown:
        lines.insert(2, "기록해 둔 순간들을 차분히 따라가 봅니다.")
    return "\n".join(lines).strip() + "\n"
