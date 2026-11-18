"""Validator agent: reviews each draft, sends it back with feedback or publishes it."""

from __future__ import annotations

import logging
from datetime import date as date_cls
from pathlib import PurePosixPath
from typing import Any

from scribegraph.agents.common import (
    as_bool,
    clean_tags,
    excerpt,
    extract_json,
    message_text,
    read_time,
    slugify,
    unique_slug,
)
from scribegraph.config import get_settings
from scribegraph.graph.state import BlogState
from scribegraph.services import llm
from scribegraph.services.prompt_manager import prompt_manager
from scribegraph.services.storage import Article, article_key, get_storage

from .prompts import VALIDATOR_PROMPT

log = logging.getLogger(__name__)

DEFAULT_FEEDBACK = "Add depth, fix inaccuracies and complete any unfinished sections."


def taken_slugs(articles: list[Article]) -> set[str]:
    return {PurePosixPath(str(a.get("file") or a.get("id") or "")).stem for a in articles}


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit].strip()


def validator_node(state: BlogState) -> dict[str, Any]:
    log.info("→ [ValidatorAgent] running")
    settings = get_settings()
    domain = state["domain"]
    topic = state.get("topic", "")
    content = state.get("content", "")
    revision = state.get("revision_count", 0)
    published_on = state.get("date") or date_cls.today().isoformat()

    if state.get("dry_run"):
        review: dict[str, Any] = {"approved": True, "title": topic}
    else:
        prompt = prompt_manager.get_prompt(
            "Validator_Prompt", VALIDATOR_PROMPT, topic=topic, content=content
        )
        reply = llm.get_chat_model(temperature=0.1).invoke(prompt)
        review = extract_json(message_text(reply)) or {}
        if not review:
            log.warning("  editor reply was not valid JSON; approving with fallback metadata")

    approved = as_bool(review.get("approved"), default=True)
    if not approved and revision < settings.pipeline.max_revisions:
        feedback = _text(review.get("feedback"), 2000) or DEFAULT_FEEDBACK
        log.info("  draft rejected (revision %d): %s", revision + 1, feedback[:200])
        return {
            "revision_needed": True,
            "validator_feedback": feedback,
            "revision_count": revision + 1,
        }
    if not approved:
        log.warning("  max revisions reached; publishing the latest draft")

    title = _text(review.get("title"), 120) or topic
    description = _text(review.get("description"), 300) or excerpt(content) or title
    tags = [domain, *[t for t in clean_tags(review.get("tags")) if t != domain]]

    storage = get_storage(settings)
    articles = storage.get_articles(domain)
    slug = unique_slug(slugify(_text(review.get("slug"), 200) or title), taken_slugs(articles))
    key = article_key(domain, slug)

    if state.get("dry_run"):
        log.info("  [dry run] would publish %s", storage.uri(key))
    else:
        storage.put_object(key, content, "text/markdown")
        entry: Article = {
            "id": key,
            "category": domain,
            "topic": topic,
            "subtopics": state.get("subtopics", ""),
            "title": title,
            "description": description,
            "date": published_on,
            "tags": tags,
            "readTime": state.get("read_time") or read_time(content),
            "file": key,
        }
        storage.save_articles(domain, [entry, *articles])
        log.info("  published “%s”", title)

    return {
        "revision_needed": False,
        "validator_feedback": "",
        "title": title,
        "description": description,
        "tags": tags,
        "slug": slug,
        "md_path": storage.uri(key),
        "published": not state.get("dry_run", False),
    }
