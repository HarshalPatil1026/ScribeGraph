import pytest
import requests

from scribegraph.config import DEFAULT_MODEL, ConfigError, get_settings
from scribegraph.services import llm as llm_service
from scribegraph.tools import GuardianSearchTool, TavilySearchTool, available_news_tools
from scribegraph.tools.tavily_search import time_range_for


def test_default_model_is_a_current_groq_model():
    # llama-3.3-70b-versatile was retired for free/developer accounts on 2026-08-16.
    assert get_settings().llm.model_name == DEFAULT_MODEL == "openai/gpt-oss-120b"


def test_groq_api_key_alias(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_alias")
    get_settings.cache_clear()
    assert get_settings().llm.api_key == "gsk_alias"


def test_nested_variables_are_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM__API_KEY", "gsk_nested")
    monkeypatch.setenv("llm__model_name", "openai/gpt-oss-20b")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.llm.api_key == "gsk_nested"
    assert settings.llm.model_name == "openai/gpt-oss-20b"


def test_missing_groq_key_gives_a_clear_error():
    with pytest.raises(ConfigError, match="Groq API key is missing"):
        llm_service.get_chat_model()


def test_chat_model_is_built_from_settings(monkeypatch):
    monkeypatch.setenv("llm__api_key", "gsk_test")
    get_settings.cache_clear()
    model = llm_service.get_chat_model(temperature=0.2)
    assert model.model_name == DEFAULT_MODEL
    assert model.temperature == 0.2


def test_news_tools_follow_configured_keys(monkeypatch):
    assert available_news_tools() == []
    monkeypatch.setenv("content__tavily_api_key", "tvly-x")
    get_settings.cache_clear()
    assert [t.name for t in available_news_tools()] == ["tavily_search"]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_tavily_sends_the_key_as_a_bearer_header(monkeypatch):
    monkeypatch.setenv("content__tavily_api_key", "tvly-secret")
    get_settings.cache_clear()
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, json=json)
        return FakeResponse({"results": [{"title": "T", "url": "https://e.com/a", "content": "C"}]})

    monkeypatch.setattr(requests, "post", fake_post)
    output = TavilySearchTool().invoke({"query": "llm agents", "days": 7})

    assert captured["headers"]["Authorization"] == "Bearer tvly-secret"
    assert "api_key" not in captured["json"]
    assert "days" not in captured["json"]
    assert captured["json"]["time_range"] == "week"
    assert "https://e.com/a" in output


@pytest.mark.parametrize(
    ("days", "expected"), [(1, "day"), (7, "week"), (30, "month"), (90, "year")]
)
def test_time_range_mapping(days, expected):
    assert time_range_for(days) == expected


def test_guardian_errors_do_not_leak_the_api_key(monkeypatch):
    key = "guardian-secret-123"
    monkeypatch.setenv("content__guardian_api_key", key)
    get_settings.cache_clear()

    def fake_get(url, params=None, timeout=None):
        raise requests.HTTPError(f"401 Unauthorized for url: {url}?api-key={params['api-key']}")

    monkeypatch.setattr(requests, "get", fake_get)
    output = GuardianSearchTool().invoke({"query": "ai"})
    assert key not in output
    assert "***" in output
