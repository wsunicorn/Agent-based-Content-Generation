"""
LangGraph StateGraph definition for the content generation pipeline.

Graph flow:
    coordinator → research → outline → writer → editor
                                                   ↓
                                        (needs_revision?) → writer (loop, max 2x)
                                                   ↓
                                         fact_checker → seo → qa → END
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from .state import PipelineState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node wrapper helpers
# ---------------------------------------------------------------------------

def _make_node(agent_class, agent_kwargs: dict | None = None):
    """Factory: returns a LangGraph node function that runs an agent."""

    def node_fn(state: dict[str, Any]) -> dict[str, Any]:
        from apps.pipeline.state import PipelineState as PS
        import dataclasses

        ps: PS = PS.from_dict(state)
        agent = agent_class(**(agent_kwargs or {}))
        updated = agent.run(ps)
        return dataclasses.asdict(updated)

    return node_fn


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------

def _route_after_editor(state: dict[str, Any]) -> str:
    if state.get("needs_revision") and state.get("revision_count", 0) < state.get("max_revisions", 2):
        logger.info("Editor requested revision #%d", state["revision_count"])
        return "writer"
    return "fact_checker"


def _route_after_qa(state: dict[str, Any]) -> str:
    if state.get("completed"):
        return END
    # If QA fails and we still have revision budget, route back to editor
    if not state.get("qa_report", {}).get("passed", False) and state.get("revision_count", 0) < state.get("max_revisions", 2):
        return "editor"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_pipeline_graph() -> StateGraph:
    """Build and compile the LangGraph pipeline graph."""
    from apps.agents.coordinator import CoordinatorAgent
    from apps.agents.research import ResearchAgent
    from apps.agents.outline import OutlineAgent
    from apps.agents.writer import WriterAgent
    from apps.agents.editor import EditorAgent
    from apps.agents.fact_checker import FactCheckerAgent
    from apps.agents.seo import SEOAgent
    from apps.agents.qa import QAAgent

    graph = StateGraph(dict)  # state is a plain dict; we use PipelineState as schema

    # Add nodes
    graph.add_node("coordinator", _make_node(CoordinatorAgent))
    graph.add_node("research", _make_node(ResearchAgent))
    graph.add_node("outline", _make_node(OutlineAgent))
    graph.add_node("writer", _make_node(WriterAgent))
    graph.add_node("editor", _make_node(EditorAgent))
    graph.add_node("fact_checker", _make_node(FactCheckerAgent))
    graph.add_node("seo", _make_node(SEOAgent))
    graph.add_node("qa", _make_node(QAAgent))

    # Linear edges
    graph.set_entry_point("coordinator")
    graph.add_edge("coordinator", "research")
    graph.add_edge("research", "outline")
    graph.add_edge("outline", "writer")

    # Conditional: editor may send back to writer for revision
    graph.add_conditional_edges(
        "editor",
        _route_after_editor,
        {"writer": "writer", "fact_checker": "fact_checker"},
    )
    graph.add_edge("writer", "editor")
    graph.add_edge("fact_checker", "seo")
    graph.add_edge("seo", "qa")

    # Conditional: QA may send back to editor or finish
    graph.add_conditional_edges(
        "qa",
        _route_after_qa,
        {"editor": "editor", END: END},
    )

    return graph.compile()


# Singleton compiled graph (imported by Celery task)
pipeline_graph = None


def get_pipeline_graph():
    global pipeline_graph
    if pipeline_graph is None:
        pipeline_graph = build_pipeline_graph()
    return pipeline_graph
