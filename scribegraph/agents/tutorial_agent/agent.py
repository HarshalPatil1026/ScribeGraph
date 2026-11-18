"""Tutorial agent: picks the stalest category and a fresh topic, then writes the article."""

from __future__ import annotations

import logging
from typing import Any

from scribegraph.agents.common import (
    clean_article,
    extract_json,
    message_text,
    pick_stalest_domain,
    read_time,
    revision_block,
)
from scribegraph.config import TUTORIAL_DOMAINS, category_label, get_settings
from scribegraph.graph.state import BlogState
from scribegraph.services import llm
from scribegraph.services.prompt_manager import prompt_manager
from scribegraph.services.storage import get_storage

from .prompts import TUTORIAL_GENERATION_PROMPT, TUTORIAL_TOPIC_PROMPT

log = logging.getLogger(__name__)


def format_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "Nothing yet. This will be the first article in this category."
    return "\n---\n".join(
        f"Title: {h.get('title', '')}\nTopic: {h.get('topic', '')}\n"
        f"Subtopics: {h.get('subtopics', '')}"
        for h in history
    )


def _subtopics_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "").strip()


def tutorial_node(state: BlogState) -> dict[str, Any]:
    log.info("→ [TutorialAgent] running")
    settings = get_settings()
    dry_run = state.get("dry_run", False)
    storage = get_storage(settings)

    domain = state.get("domain") or pick_stalest_domain(storage.last_published(TUTORIAL_DOMAINS))
    label = category_label(domain)
    topic = state.get("topic", "")
    subtopics = state.get("subtopics", "")

    # Step 1: plan a topic (skipped when the caller or an earlier pass already set one).
    if not topic:
        if dry_run:
            topic = f"Dry run: a new {label} topic"
            subtopics = "first subtopic, second subtopic, third subtopic"
        else:
            history = storage.recent_history(domain, limit=settings.pipeline.history_size)
            prompt = prompt_manager.get_prompt(
                "Tutorial_Topic_Prompt",
                TUTORIAL_TOPIC_PROMPT,
                cat_label=label,
                history=format_history(history),
            )
            reply = llm.get_chat_model(temperature=0.8).invoke(prompt)
            plan = extract_json(message_text(reply)) or {}
            topic = str(plan.get("topic") or "").strip() or f"Emerging Trends in {label}"
            subtopics = _subtopics_text(plan.get("subtopics"))
        log.info("  category: %s | topic: %s", domain, topic)

    # Step 2: write (or revise) the article.
    if dry_run:
        content = f"_Dry run: no LLM call was made for **{topic}**._\n"
    else:
        prompt = prompt_manager.get_prompt(
            "Tutorial_Generation_Prompt",
            TUTORIAL_GENERATION_PROMPT,
            cat_label=label,
            topic=topic,
            subtopics=subtopics or "choose the most useful ones",
            validator_feedback=revision_block(state),
        )
        reply = llm.get_chat_model(temperature=0.6).invoke(prompt)
        content = clean_article(message_text(reply))
        log.info("  drafted %d words", len(content.split()))

    return {
        "domain": domain,
        "topic": topic,
        "subtopics": subtopics,
        "content": content,
        "read_time": read_time(content),
    }
