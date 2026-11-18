"""LLM access: the Groq chat-model factory and the tool-using news research agent.

Agents call these functions at run time (``llm.get_chat_model(...)``), so tests can
swap in scripted models with ``monkeypatch``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scribegraph.config import ConfigError, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


def get_chat_model(temperature: float | None = None) -> BaseChatModel:
    """A Groq chat model configured from settings."""
    settings = get_settings()
    if not settings.llm.api_key:
        raise ConfigError(
            "Groq API key is missing. Set llm__api_key (or GROQ_API_KEY) in your .env file "
            "or environment. Free keys: https://console.groq.com/keys"
        )
    from langchain_groq import ChatGroq  # imported lazily so dry runs start fast

    return ChatGroq(
        model=settings.llm.model_name,
        temperature=settings.llm.temperature if temperature is None else temperature,
        api_key=settings.llm.api_key,
        max_retries=settings.llm.max_retries,
        timeout=settings.llm.timeout,
    )


def get_news_research_agent(system_prompt: str, model: BaseChatModel | None = None):
    """A tool-calling agent that can search Tavily and/or The Guardian.

    Uses ``langchain.agents.create_agent``. The original code passed
    ``state_modifier=`` to ``create_react_agent``, which LangGraph 1.0 rejects with a
    TypeError, so the AI News pipeline could not run.
    """
    from langchain.agents import create_agent

    from scribegraph.tools import available_news_tools

    tools = available_news_tools()
    if not tools:
        raise ConfigError(
            "AI News needs at least one search API key: content__tavily_api_key "
            "or content__guardian_api_key."
        )
    return create_agent(
        model=model if model is not None else get_chat_model(),
        tools=tools,
        system_prompt=system_prompt,
    )
