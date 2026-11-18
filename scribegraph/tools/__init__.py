"""Search tools for the AI News research agent."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from scribegraph.config import get_settings

from .guardian_search import GuardianSearchTool
from .redact import redact
from .tavily_search import TavilySearchTool

__all__ = ["GuardianSearchTool", "TavilySearchTool", "available_news_tools", "redact"]


def available_news_tools() -> list[BaseTool]:
    """The search tools whose API keys are configured."""
    content = get_settings().content
    tools: list[BaseTool] = []
    if content.tavily_api_key:
        tools.append(TavilySearchTool())
    if content.guardian_api_key:
        tools.append(GuardianSearchTool())
    return tools
