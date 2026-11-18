"""The Guardian Open Platform search tool."""

from __future__ import annotations

from datetime import date, timedelta

import requests
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from scribegraph.config import get_settings
from scribegraph.tools.redact import redact

GUARDIAN_SEARCH_URL = "https://content.guardianapis.com/search"


class GuardianSearchInput(BaseModel):
    query: str = Field(description="What to search for on The Guardian.")
    days: int = Field(default=7, ge=1, le=365, description="How many days back to search.")


class GuardianSearchTool(BaseTool):
    """Journalism search through The Guardian's content API."""

    name: str = "guardian_search"
    description: str = (
        "Search The Guardian's news archive. Reliable for well-researched reporting on "
        "technology, policy and industry. Returns headlines, URLs and excerpts."
    )
    args_schema: type[BaseModel] = GuardianSearchInput
    max_results: int = 5
    timeout: float = 20.0

    def _run(self, query: str, days: int = 7) -> str:
        api_key = get_settings().content.guardian_api_key
        if not api_key:
            return "Error: the Guardian API key is not configured (content__guardian_api_key)."
        today = date.today()
        try:
            response = requests.get(
                GUARDIAN_SEARCH_URL,
                params={
                    "api-key": api_key,
                    "q": query,
                    "from-date": (today - timedelta(days=days)).isoformat(),
                    "to-date": today.isoformat(),
                    "order-by": "relevance",
                    "page-size": self.max_results,
                    "show-fields": "headline,trailText,bodyText",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            results = response.json().get("response", {}).get("results", [])
        except requests.RequestException as exc:
            # The key travels in the query string, so error messages can contain it.
            return redact(f"Guardian search failed: {exc}", api_key)

        if not results:
            return f"No Guardian results for {query!r}."
        formatted = []
        for result in results:
            fields = result.get("fields", {})
            body = (fields.get("bodyText") or "")[:1000]
            formatted.append(
                f"Title: {fields.get('headline') or result.get('webTitle')}\n"
                f"URL: {result.get('webUrl')}\n"
                f"Published: {result.get('webPublicationDate', 'unknown')}\n"
                f"Excerpt: {fields.get('trailText', '')}\n"
                f"Summary: {body}..."
            )
        return "\n\n".join(formatted)
