"""Shared state passed between the LangGraph nodes."""

from __future__ import annotations

from typing import TypedDict


class BlogState(TypedDict, total=False):
    # Inputs
    date: str  # publication date, YYYY-MM-DD
    domain: str  # category key; chosen automatically when empty
    topic: str  # chosen by the tutorial agent when empty
    subtopics: str
    dry_run: bool

    # Research (AI News only)
    news_data: str

    # Draft
    content: str
    read_time: str

    # Review loop
    validator_feedback: str
    revision_count: int
    revision_needed: bool

    # Result
    title: str
    description: str
    tags: list[str]
    slug: str
    md_path: str
    published: bool
