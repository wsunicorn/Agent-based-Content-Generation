"""LangGraph StateGraph definition for the content generation pipeline.

Phase 2 uses a map-reduce writer stage:
    outline -> writer planner -> section_writer[] -> join_draft -> editor
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import Send

logger = logging.getLogger(__name__)


def _concat(left: list | None, right: list | None) -> list:
    return (left or []) + (right or [])


class PipelineGraphState(TypedDict, total=False):
    job_id: str
    topic: str
    content_type: str
    target_length: int
    keywords: list[str]
    additional_instructions: str
    sources: list[dict[str, Any]]
    research_summary: str
    sections: list[dict[str, Any]]
    outline_approved: bool
    writer_tasks: list[dict[str, Any]]
    section_drafts: Annotated[list[dict[str, Any]], _concat]
    section_usage_deltas: Annotated[list[dict[str, Any]], _concat]
    introduction: str
    body_sections: dict[str, str]
    conclusion: str
    draft: str
    word_count: int
    edited_draft: str
    editor_changes: list[str]
    needs_revision: bool
    revision_reason: str
    seo_metadata: dict[str, Any]
    fact_check_passed: bool
    unverified_claims: list[dict[str, Any]]
    qa_report: dict[str, Any]
    final_content: str
    current_agent: str
    last_quality_gate: str
    routing_decision: str
    next_action: str
    target_agent: str
    revision_target_section_ids: list[int]
    revision_instructions: str
    routing_issues: list[str]
    retry_counts: dict[str, int]
    revision_events: list[dict[str, Any]]
    revision_count: int
    max_revisions: int
    max_agent_retries: int
    error: str | None
    completed: bool
    llm_calls_total: int
    llm_tokens_total: int
    llm_calls_by_provider: dict[str, int]
    llm_tokens_by_provider: dict[str, int]


BRANCH_ACCUMULATORS = {"section_drafts", "section_usage_deltas"}


def _without_branch_accumulators(output: dict[str, Any]) -> dict[str, Any]:
    """Normal nodes should not re-emit reducer fields and duplicate branch output."""
    return {key: value for key, value in output.items() if key not in BRANCH_ACCUMULATORS}


# ---------------------------------------------------------------------------
# Node wrapper helpers
# ---------------------------------------------------------------------------

def _make_node(agent_class, agent_kwargs: dict | None = None):
    """Factory: returns a LangGraph node function that runs an agent."""

    def node_fn(state: dict[str, Any]) -> dict[str, Any]:
        from apps.pipeline.state import PipelineState as PS

        ps: PS = PS.from_dict(state)
        agent = agent_class(**(agent_kwargs or {}))
        updated = agent.run(ps)
        return _without_branch_accumulators(dataclasses.asdict(updated))

    return node_fn


def _section_writer_node(state: dict[str, Any]) -> dict[str, Any]:
    from apps.agents.section_writer import SectionWriterAgent
    from apps.pipeline.state import PipelineState, SectionWriteTask

    task_data = state.get("write_task", {})
    task = SectionWriteTask(**task_data)
    ps = PipelineState.from_dict(state)
    draft, usage_delta = SectionWriterAgent().run_task(ps, task)
    return {
        "section_drafts": [dataclasses.asdict(draft)],
        "section_usage_deltas": [usage_delta],
    }


def _join_draft_node(state: dict[str, Any]) -> dict[str, Any]:
    from apps.agents.join_draft import JoinDraftAgent
    from apps.pipeline.state import PipelineState

    ps = PipelineState.from_dict(state)
    updated = JoinDraftAgent().run(ps)
    return _without_branch_accumulators(dataclasses.asdict(updated))


def _coordinator_router_node(state: dict[str, Any]) -> dict[str, Any]:
    from apps.agents.coordinator import CoordinatorAgent
    from apps.pipeline.state import PipelineState

    ps = PipelineState.from_dict(state)
    updated = CoordinatorAgent().run_router(ps)
    return _without_branch_accumulators(dataclasses.asdict(updated))


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------

def _send_writer_tasks(state: dict[str, Any]) -> list[Send]:
    tasks = state.get("writer_tasks") or []
    target_ids = set(state.get("revision_target_section_ids") or [])
    if target_ids:
        tasks = [
            task
            for task in tasks
            if task.get("section_id") in target_ids
        ]

    if not tasks:
        logger.warning("No writer tasks available; continuing with join_draft")
        return [Send("join_draft", state)]

    sends = []
    for task in tasks:
        payload = dict(state)
        payload["write_task"] = task
        sends.append(Send("section_writer", payload))
    logger.info("Dispatching %d section writer task(s)", len(sends))
    return sends


def _route_after_coordinator_router(state: dict[str, Any]) -> str:
    if state.get("completed") or state.get("next_action") == "fail_with_warning":
        return END

    target = state.get("target_agent") or ""
    if target in {"research", "outline", "writer", "editor", "fact_checker", "seo", "qa"}:
        return target

    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_pipeline_graph() -> StateGraph:
    """Build and compile the LangGraph pipeline graph."""
    from apps.agents.coordinator import CoordinatorAgent
    from apps.agents.editor import EditorAgent
    from apps.agents.fact_checker import FactCheckerAgent
    from apps.agents.outline import OutlineAgent
    from apps.agents.qa import QAAgent
    from apps.agents.research import ResearchAgent
    from apps.agents.seo import SEOAgent
    from apps.agents.writer import WriterAgent

    graph = StateGraph(PipelineGraphState)

    graph.add_node("coordinator", _make_node(CoordinatorAgent))
    graph.add_node("research", _make_node(ResearchAgent))
    graph.add_node("outline", _make_node(OutlineAgent))
    graph.add_node("writer", _make_node(WriterAgent))
    graph.add_node("section_writer", _section_writer_node)
    graph.add_node("join_draft", _join_draft_node)
    graph.add_node("editor", _make_node(EditorAgent))
    graph.add_node("coordinator_router", _coordinator_router_node)
    graph.add_node("fact_checker", _make_node(FactCheckerAgent))
    graph.add_node("seo", _make_node(SEOAgent))
    graph.add_node("qa", _make_node(QAAgent))

    graph.set_entry_point("coordinator")
    graph.add_edge("coordinator", "research")
    graph.add_edge("research", "outline")
    graph.add_edge("outline", "writer")
    graph.add_conditional_edges("writer", _send_writer_tasks, ["section_writer", "join_draft"])
    graph.add_edge("section_writer", "join_draft")
    graph.add_edge("join_draft", "editor")

    graph.add_edge("editor", "coordinator_router")
    graph.add_edge("fact_checker", "coordinator_router")
    graph.add_edge("seo", "coordinator_router")
    graph.add_edge("qa", "coordinator_router")

    graph.add_conditional_edges(
        "coordinator_router",
        _route_after_coordinator_router,
        {
            "research": "research",
            "outline": "outline",
            "writer": "writer",
            "editor": "editor",
            "fact_checker": "fact_checker",
            "seo": "seo",
            "qa": "qa",
            END: END,
        },
    )

    return graph.compile()


pipeline_graph = None


def get_pipeline_graph():
    global pipeline_graph
    if pipeline_graph is None:
        pipeline_graph = build_pipeline_graph()
    return pipeline_graph
