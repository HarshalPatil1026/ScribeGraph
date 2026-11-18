"""The ScribeGraph workflow.

START ─┬─> tutorial_agent ─┐
       └─> news_agent ─────┴─> validator ─┬─> END (published)
             ^                            │
             └──── revise with feedback ──┘
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from scribegraph.agents.news_agent.agent import news_node
from scribegraph.agents.tutorial_agent.agent import tutorial_node
from scribegraph.agents.validator_agent.agent import validator_node
from scribegraph.config import NEWS_DOMAIN
from scribegraph.graph.state import BlogState


def route_start(state: BlogState) -> str:
    """AI News goes to the research agent; everything else to the tutorial agent."""
    return "news_agent" if state.get("domain") == NEWS_DOMAIN else "tutorial_agent"


def route_after_validator(state: BlogState) -> str:
    """Send a rejected draft back to the agent that wrote it, otherwise finish."""
    return route_start(state) if state.get("revision_needed") else END


def build_graph(checkpointer: Any = None):
    builder = StateGraph(BlogState)
    builder.add_node("tutorial_agent", tutorial_node)
    builder.add_node("news_agent", news_node)
    builder.add_node("validator", validator_node)

    builder.add_conditional_edges(START, route_start, ["tutorial_agent", "news_agent"])
    builder.add_edge("tutorial_agent", "validator")
    builder.add_edge("news_agent", "validator")
    builder.add_conditional_edges(
        "validator", route_after_validator, ["tutorial_agent", "news_agent", END]
    )
    return builder.compile(checkpointer=checkpointer)


graph = build_graph()
