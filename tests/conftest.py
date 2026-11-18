"""Shared fixtures: hermetic settings, a temporary site folder and a scripted LLM."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from scribegraph.config import get_settings
from scribegraph.config import settings as settings_module
from scribegraph.services import llm as llm_service

_ENV_VARS = [
    "GROQ_API_KEY",
    "llm__api_key",
    "llm__model_name",
    "storage__backend",
    "storage__local_dir",
    "r2__account_id",
    "r2__access_key_id",
    "r2__secret_access_key",
    "r2__bucket_name",
    "content__tavily_api_key",
    "content__guardian_api_key",
    "pipeline__max_revisions",
    "pipeline__history_size",
    "OPIK_API_KEY",
    "SENTRY_DSN",
    "GITHUB_STEP_SUMMARY",
]


@pytest.fixture(autouse=True)
def site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Ignore any real .env file or keys, and store articles in a temporary site folder."""
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.setitem(settings_module.Settings.model_config, "env_file", None)

    root = tmp_path / "site"
    (root / "blogs").mkdir(parents=True)
    monkeypatch.setenv("storage__backend", "local")
    monkeypatch.setenv("storage__local_dir", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture
def seed(site: Path) -> Callable[[str, list[dict]], None]:
    """Write an articles.json (and a stub .md per article) for a category."""

    def _seed(domain: str, articles: list[dict]) -> None:
        folder = site / "blogs" / domain
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "articles.json").write_text(json.dumps(articles), encoding="utf-8")
        for article in articles:
            (site / article["file"]).write_text("old body\n", encoding="utf-8")

    return _seed


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


class ScriptedLLM:
    """Stands in for ChatGroq: returns scripted replies in order and records every prompt."""

    def __init__(self, replies: tuple[str, ...]):
        self.replies = list(replies)
        self.prompts: list[str] = []
        self.temperatures: list[float | None] = []

    def invoke(self, prompt, *args, **kwargs) -> AIMessage:
        self.prompts.append(prompt)
        if not self.replies:
            raise AssertionError("The LLM was called more times than scripted.")
        return AIMessage(content=self.replies.pop(0))


@pytest.fixture
def scripted_llm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., ScriptedLLM]:
    def install(*replies: str) -> ScriptedLLM:
        fake = ScriptedLLM(replies)

        def factory(temperature: float | None = None) -> ScriptedLLM:
            fake.temperatures.append(temperature)
            return fake

        monkeypatch.setattr(llm_service, "get_chat_model", factory)
        return fake

    return install


@pytest.fixture
def no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if anything tries to reach an LLM or the news tools."""

    def boom(*args, **kwargs):
        raise AssertionError("The LLM must not be called here.")

    monkeypatch.setattr(llm_service, "get_chat_model", boom)
    monkeypatch.setattr(llm_service, "get_news_research_agent", boom)
