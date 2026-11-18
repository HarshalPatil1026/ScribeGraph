"""End-to-end runs of the LangGraph workflow with a scripted LLM and local storage."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import END

from scribegraph.agents.news_agent.agent import RESEARCH_STEP_LIMIT
from scribegraph.config import ConfigError, get_settings
from scribegraph.graph.graph import build_graph, route_after_validator, route_start
from scribegraph.services import llm as llm_service

from .conftest import snapshot

TODAY = "2026-11-18"


def article(domain: str, slug: str, date: str = "2026-01-01") -> dict:
    key = f"blogs/{domain}/{slug}.md"
    return {"id": key, "file": key, "category": domain, "title": slug, "date": date}


def test_routing():
    assert route_start({"domain": "ainews"}) == "news_agent"
    assert route_start({"domain": "ml"}) == "tutorial_agent"
    assert route_start({}) == "tutorial_agent"
    assert route_after_validator({"revision_needed": True, "domain": "ainews"}) == "news_agent"
    assert route_after_validator({"revision_needed": True, "domain": "cv"}) == "tutorial_agent"
    assert route_after_validator({"revision_needed": False, "domain": "cv"}) == END


def test_dry_run_is_offline_and_writes_nothing(site, seed, no_llm):
    seed("ml", [article("ml", "intro", "2026-03-02")])
    before = snapshot(site)

    result = build_graph().invoke({"date": TODAY, "dry_run": True})

    assert result["domain"] == "dl"  # first category that has never been published
    assert result["published"] is False
    assert result["md_path"].endswith("blogs/dl/dry-run-a-new-deep-learning-topic.md")
    assert snapshot(site) == before


def test_tutorial_run_revises_then_publishes_without_overwriting(site, seed, scripted_llm):
    seed("ml", [article("ml", "gradient-boosting-from-scratch")])
    plan = {"topic": "Gradient Boosting from Scratch", "subtopics": ["Stumps", "Residuals"]}
    approval = {
        "approved": True,
        "title": "Gradient Boosting from Scratch",
        "description": "Step by step.",
        "slug": "Gradient Boosting: From Scratch!",
        "tags": ["Boosting", "ML", "xgboost"],
    }
    llm = scripted_llm(
        f"```json\n{json.dumps(plan)}\n```",
        "# Gradient Boosting\n\nToo short.",
        '{"approved": false, "feedback": "1. Add a code example."}',
        "```markdown\n# Gradient Boosting from Scratch\n\n"
        "Boosting adds weak learners one at a time.\n\n"
        "## Code\n\n```python\nprint('fit')\n```\n```",
        json.dumps(approval),
    )

    result = build_graph().invoke({"date": TODAY, "domain": "ml"})

    assert result["published"] is True
    assert result["revision_count"] == 1
    assert result["subtopics"] == "Stumps, Residuals"
    # A slug collision gets a suffix instead of overwriting the older article.
    assert result["slug"] == "gradient-boosting-from-scratch-2"
    assert (site / "blogs/ml/gradient-boosting-from-scratch.md").read_text() == "old body\n"

    body = (site / "blogs/ml/gradient-boosting-from-scratch-2.md").read_text()
    assert body.startswith("Boosting adds weak learners")  # outer fence and H1 removed
    assert "```python\nprint('fit')\n```" in body

    index = json.loads((site / "blogs/ml/articles.json").read_text())
    assert [a["id"] for a in index] == [
        "blogs/ml/gradient-boosting-from-scratch-2.md",
        "blogs/ml/gradient-boosting-from-scratch.md",
    ]
    new = index[0]
    assert new["title"] == "Gradient Boosting from Scratch"
    assert new["tags"] == ["ml", "boosting", "xgboost"]
    assert new["date"] == TODAY
    assert new["readTime"] == "1 min"

    # The rewrite saw the editor's feedback and the rejected draft.
    assert "Add a code example" in llm.prompts[3]
    assert "Too short." in llm.prompts[3]
    assert llm.temperatures == [0.8, 0.6, 0.1, 0.6, 0.1]
    assert not llm.replies


def test_auto_category_picks_one_that_was_never_published(site, seed, scripted_llm):
    seed("ml", [article("ml", "a", "2026-03-01")])
    seed("dl", [article("dl", "b", "2026-02-01")])
    seed("statistics", [article("statistics", "c", "2026-01-01")])
    llm = scripted_llm(
        '{"topic": "Subword Tokenization", "subtopics": "BPE, WordPiece"}',
        "Tokenizers split text into units.",
        '{"approved": true, "title": "Subword Tokenization", "slug": "subword-tokenization"}',
    )

    result = build_graph().invoke({"date": TODAY})

    assert result["domain"] == "nlp"
    assert "Natural Language Processing" in llm.prompts[0]
    assert (site / "blogs/nlp/subword-tokenization.md").exists()


def test_topic_planner_sees_recent_history(site, seed, scripted_llm):
    seed("cv", [article("cv", "object-detection-with-yolo", "2026-05-01")])
    llm = scripted_llm(
        '{"topic": "Image Segmentation", "subtopics": "U-Net"}',
        "Body.",
        '{"approved": true}',
    )
    build_graph().invoke({"date": TODAY, "domain": "cv"})
    assert "object-detection-with-yolo" in llm.prompts[0]


def test_publishes_latest_draft_after_max_revisions(site, scripted_llm, monkeypatch):
    monkeypatch.setenv("pipeline__max_revisions", "1")
    get_settings.cache_clear()
    scripted_llm(
        "Draft one.",
        '{"approved": false, "feedback": "More depth."}',
        "Draft two is better.",
        '{"approved": "false", "feedback": "Still thin."}',
    )

    result = build_graph().invoke({"date": TODAY, "domain": "cv", "topic": "Vision Transformers"})

    assert result["published"] is True
    assert result["revision_count"] == 1
    assert result["title"] == "Vision Transformers"  # falls back to the topic
    assert result["description"] == "Draft two is better."
    assert (site / "blogs/cv/vision-transformers.md").read_text() == "Draft two is better.\n"


def test_unparseable_editor_reply_still_publishes(site, scripted_llm):
    scripted_llm("A complete article body.", "Looks great to me!")
    result = build_graph().invoke({"date": TODAY, "domain": "genai", "topic": "RAG Basics"})
    assert result["published"] is True
    assert result["slug"] == "rag-basics"


def test_news_run_researches_then_writes(site, scripted_llm, monkeypatch):
    calls = []

    class FakeAgent:
        def invoke(self, inputs, config=None):
            calls.append(config)
            return {"messages": [AIMessage(content="1. Big release. https://example.com/story")]}

    prompts = {}

    def factory(system_prompt, model=None):
        prompts["system"] = system_prompt
        return FakeAgent()

    monkeypatch.setattr(llm_service, "get_news_research_agent", factory)
    llm = scripted_llm(
        "Overview.\n\n## Big release\n\n[Source](https://example.com/story)",
        '{"approved": true, "title": "The Week in AI", "slug": "the-week-in-ai"}',
    )

    result = build_graph().invoke({"date": "2026-11-22", "domain": "ainews"})

    assert result["domain"] == "ainews"
    assert (site / "blogs/ainews/the-week-in-ai.md").exists()
    assert "2026-11-22" in prompts["system"]
    assert "https://example.com/story" in llm.prompts[0]  # research notes reach the writer
    assert calls == [{"recursion_limit": RESEARCH_STEP_LIMIT}]


def test_news_research_agent_calls_its_tools(monkeypatch):
    # Regression: the original passed state_modifier= to create_react_agent, which
    # LangGraph 1.0 rejects with a TypeError, so AI News could never run.
    searched = []

    @tool
    def tavily_search(query: str) -> str:
        """Search recent news."""
        searched.append(query)
        return "Result: https://example.com"

    monkeypatch.setattr("scribegraph.tools.available_news_tools", lambda: [tavily_search])

    class ToolCallingModel(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    model = ToolCallingModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "tavily_search", "args": {"query": "llm"}, "id": "c1"}],
                ),
                AIMessage(content="Summary: https://example.com"),
            ]
        )
    )
    agent = llm_service.get_news_research_agent("You are a researcher.", model=model)
    result = agent.invoke({"messages": [("user", "news please")]})

    assert searched == ["llm"]
    assert result["messages"][-1].content == "Summary: https://example.com"


def test_news_research_needs_a_search_key():
    with pytest.raises(ConfigError, match="search API key"):
        llm_service.get_news_research_agent("x", model=object())
