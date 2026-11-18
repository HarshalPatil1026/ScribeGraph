"""Tavily news search tool."""

from __future__ import annotations

import requests
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from scribegraph.config import get_settings
from scribegraph.tools.redact import redact

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def time_range_for(days: int) -> str:
    """Map a look-back window in days to Tavily's ``time_range`` values."""
    if days <= 1:
        return "day"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    return "year"


class TavilySearchInput(BaseModel):
    query: str = Field(description="What to search for.")
    days: int = Field(default=7, ge=1, le=365, description="How many days back to search.")


class TavilySearchTool(BaseTool):
    """Recent news search through the Tavily API.

    Tavily expects the key in an ``Authorization: Bearer`` header and filters by
    ``time_range``. The original tool sent ``api_key`` and ``days`` in the JSON body,
    which the current API does not accept.
    """

    name: str = "tavily_search"
    description: str = (
        "Search recent web news with Tavily. Best for up-to-date AI and technology news. "
        "Returns titles, URLs, dates and short summaries."
    )
    args_schema: type[BaseModel] = TavilySearchInput
    max_results: int = 5
    timeout: float = 20.0

    def _run(self, query: str, days: int = 7) -> str:
        api_key = get_settings().content.tavily_api_key
        if not api_key:
            return "Error: the Tavily API key is not configured (content__tavily_api_key)."
        try:
            response = requests.post(
                TAVILY_SEARCH_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "query": query,
                    "topic": "news",
                    "time_range": time_range_for(days),
                    "max_results": self.max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
        except requests.RequestException as exc:
            return redact(f"Tavily search failed: {exc}", api_key)

        if not results:
            return f"No Tavily results for {query!r}."
        return "\n\n".join(
            f"Title: {r.get('title')}\n"
            f"URL: {r.get('url')}\n"
            f"Published: {r.get('published_date') or 'unknown'}\n"
            f"Summary: {r.get('content')}"
            for r in results
        )
