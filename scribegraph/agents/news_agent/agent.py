"""News agent: researches the past week's AI news with search tools, then writes a roundup."""

from __future__ import annotations

import logging
from datetime import date as date_cls
from typing import Any

from scribegraph.agents.common import clean_article, message_text, read_time, revision_block
from scribegraph.config import NEWS_DOMAIN, category_label
from scribegraph.graph.state import BlogState
from scribegraph.services import llm
from scribegraph.services.prompt_manager import prompt_manager

from .prompts import NEWS_GENERATION_PROMPT, RESEARCH_SYSTEM_PROMPT

log = logging.getLogger(__name__)

DEFAULT_NEWS_TOPIC = "The week in AI: the most important news"
RESEARCH_STEP_LIMIT = 16  # caps the tool-calling loop


def news_node(state: BlogState) -> dict[str, Any]:
    log.info("→ [NewsAgent] running")
    domain = NEWS_DOMAIN
    label = category_label(domain)
    topic = state.get("topic") or DEFAULT_NEWS_TOPIC
    today = state.get("date") or date_cls.today().isoformat()

    if state.get("dry_run"):
        content = "_Dry run: no web research or LLM call was made._\n"
        return {
            "domain": domain,
            "topic": topic,
            "news_data": "dry run",
            "content": content,
            "read_time": read_time(content),
        }

    # Step 1: research (only once; revisions reuse the notes).
    news = state.get("news_data", "")
    if not news:
        log.info("  researching the web…")
        agent = llm.get_news_research_agent(RESEARCH_SYSTEM_PROMPT.format(date=today, topic=topic))
        result = agent.invoke(
            {"messages": [("user", f"Research this week's news about: {topic}")]},
            config={"recursion_limit": RESEARCH_STEP_LIMIT},
        )
        news = message_text(result["messages"][-1])
        log.info("  research notes: %d characters", len(news))

    # Step 2: write the roundup.
    prompt = prompt_manager.get_prompt(
        "News_Generation_Prompt",
        NEWS_GENERATION_PROMPT,
        cat_label=label,
        topic=topic,
        news_context=news,
        validator_feedback=revision_block(state),
    )
    reply = llm.get_chat_model(temperature=0.4).invoke(prompt)
    content = clean_article(message_text(reply))
    log.info("  drafted %d words", len(content.split()))

    return {
        "domain": domain,
        "topic": topic,
        "news_data": news,
        "content": content,
        "read_time": read_time(content),
    }
