"""Small helpers shared by the agents. Pure functions, no I/O, easy to test."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

WORDS_PER_MINUTE = 200

# A reply wrapped entirely in ```markdown ... ``` (a common LLM habit). Only the
# markdown/md fence is unwrapped, so articles that merely start or end with a code
# block are left alone.
_MARKDOWN_FENCE = re.compile(
    r"\A```(?:markdown|md)[ \t]*\r?\n(?P<body>.*)\r?\n```[ \t]*\Z", re.DOTALL | re.IGNORECASE
)
_LEADING_H1 = re.compile(r"\A#[ \t]+[^\n]*\n+")


def message_text(message: Any) -> str:
    """Plain text of a LangChain message (or any object with ``.content``)."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, Mapping) and block.get("type", "text") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content or "")


def read_time(text: str) -> str:
    """Estimated reading time, e.g. ``"7 min"`` (never less than one minute)."""
    words = len(text.split())
    return f"{max(1, math.ceil(words / WORDS_PER_MINUTE))} min"


def strip_markdown_fence(text: str) -> str:
    """Unwrap a reply that is entirely enclosed in a ```markdown fence."""
    stripped = text.strip()
    match = _MARKDOWN_FENCE.match(stripped)
    return match.group("body").strip() if match else stripped


def strip_leading_h1(text: str) -> str:
    """Drop a leading ``# Title`` line; the site renders the title from metadata."""
    return _LEADING_H1.sub("", text.lstrip(), count=1)


def clean_article(text: str) -> str:
    return strip_leading_h1(strip_markdown_fence(text)).strip() + "\n"


def extract_json(text: str) -> dict[str, Any] | None:
    """Return the first JSON object in an LLM reply, tolerating code fences and chatter."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, dict):
        return value
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        try:
            value, _ = decoder.raw_decode(cleaned, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def as_bool(value: Any, default: bool = True) -> bool:
    """Interpret LLM booleans such as ``true``, ``"false"`` or ``"no"``."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"false", "no", "0", "rejected", "reject"}:
            return False
        if text in {"true", "yes", "1", "approved", "approve"}:
            return True
        return default
    return bool(value)


def slugify(text: str, max_length: int = 80) -> str:
    """URL-safe ASCII slug: lowercase, hyphen-separated, never empty."""
    normalized = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if len(slug) > max_length:
        cut = slug[:max_length]
        slug = (cut.rsplit("-", 1)[0] if "-" in cut else cut).strip("-")
    return slug or "article"


def unique_slug(base: str, taken: Iterable[str]) -> str:
    """``base`` if it is free, otherwise ``base-2``, ``base-3`` and so on."""
    used = set(taken)
    if base not in used:
        return base
    n = 2
    while f"{base}-{n}" in used:
        n += 1
    return f"{base}-{n}"


def clean_tags(tags: Any, limit: int = 5) -> list[str]:
    """Normalise a list of tags from the LLM into short slugs."""
    if isinstance(tags, str):
        tags = tags.split(",")
    if not isinstance(tags, list):
        return []
    result: list[str] = []
    for tag in tags:
        slug = slugify(str(tag), max_length=30)
        if slug != "article" and slug not in result:
            result.append(slug)
        if len(result) == limit:
            break
    return result


def excerpt(markdown: str, max_length: int = 160) -> str:
    """First prose paragraph of an article, stripped of Markdown, for meta descriptions."""
    for block in re.split(r"\n\s*\n", markdown):
        block = block.strip()
        if not block or block.startswith(("#", "```", "|", "!", ">", "-", "*", "1.")):
            continue
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", block)  # links -> text
        text = re.sub(r"[*_`]+", "", text)
        text = " ".join(text.split())
        if len(text) <= max_length:
            return text
        return text[: max_length - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return ""


def pick_stalest_domain(last_published: Mapping[str, str | None]) -> str:
    """Category that has gone longest without an article.

    Categories that have never been published come first; ties keep the given order.
    (The original BlogBoard sorted the string "Never" after real dates, so empty
    categories were never picked.)
    """
    if not last_published:
        raise ValueError("no categories to choose from")
    order = {domain: i for i, domain in enumerate(last_published)}
    return min(
        last_published,
        key=lambda d: (last_published[d] is not None, last_published[d] or "", order[d]),
    )


def revision_block(state: Mapping[str, Any]) -> str:
    """Editor feedback plus the rejected draft, so the writer revises instead of restarting."""
    feedback = state.get("validator_feedback")
    if not feedback:
        return ""
    return (
        "Your previous draft was REJECTED by the editor. Fix every point below.\n"
        f"Editor feedback:\n{feedback}\n\n"
        "Previous draft (revise it and keep what already works):\n"
        f"=== PREVIOUS DRAFT START ===\n{state.get('content', '')}\n=== PREVIOUS DRAFT END ==="
    )
