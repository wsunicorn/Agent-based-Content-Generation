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
    quality_mode: str
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
    fact_check_report: dict[str, Any]
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


def _agent_run_detail(agent: str, output: dict[str, Any]) -> dict[str, Any]:
    if agent == "research":
        return {
            "sources_count": len(output.get("sources") or []),
            "summary_chars": len(output.get("research_summary") or ""),
        }
    if agent == "outline":
        return {"sections_count": len(output.get("sections") or [])}
    if agent == "writer":
        return {"tasks_count": len(output.get("writer_tasks") or [])}
    if agent == "section_writer":
        drafts = output.get("section_drafts") or []
        draft = drafts[0] if drafts else {}
        return {
            "section_id": draft.get("section_id"),
            "heading": draft.get("heading", ""),
            "section_kind": draft.get("section_kind", ""),
            "word_count": draft.get("word_count", 0),
        }
    if agent in {"join_draft", "editor"}:
        text = output.get("edited_draft") if agent == "editor" else output.get("draft")
        return {"word_count": len((text or "").split())}
    if agent == "fact_checker":
        report = output.get("fact_check_report") or {}
        return {
            "passed": output.get("fact_check_passed", False),
            "unverified_count": len(output.get("unverified_claims") or []),
            "claims_checked": report.get("claims_checked", 0),
            "mode": report.get("mode", ""),
        }
    if agent == "seo":
        metadata = output.get("seo_metadata") or {}
        return {
            "focus_keyword": metadata.get("focus_keyword", ""),
            "seo_score": metadata.get("seo_score", 0),
        }
    if agent == "qa":
        report = output.get("qa_report") or {}
        return {
            "qa_score": report.get("overall_score", 0),
            "passed": report.get("passed", False),
            "next_action": report.get("next_action", ""),
        }
    if agent == "coordinator_router":
        return {
            "next_action": output.get("next_action", ""),
            "target_agent": output.get("target_agent", ""),
            "revision_count": output.get("revision_count", 0),
            "issues": (output.get("routing_issues") or [])[:3],
        }
    return {"completed": True}


# ---------------------------------------------------------------------------
# Node wrapper helpers
# ---------------------------------------------------------------------------

def _make_node(agent_class, agent_kwargs: dict | None = None):
    """Factory: returns a LangGraph node function that runs an agent."""

    def node_fn(state: dict[str, Any]) -> dict[str, Any]:
        from apps.jobs.progress import (
            complete_agent_run,
            fail_agent_run,
            provider_delta,
            start_agent_run,
        )
        from apps.pipeline.state import PipelineState as PS

        ps: PS = PS.from_dict(state)
        agent = agent_class(**(agent_kwargs or {}))
        run = start_agent_run(
            ps.job_id,
            agent.name,
            {
                "revision_count": ps.revision_count,
                "target_agent": ps.target_agent,
                "next_action": ps.next_action,
            },
        )
        before_by_provider = dict(ps.llm_calls_by_provider)
        try:
            updated = agent.run(ps)
        except Exception as exc:
            fail_agent_run(run, exc)
            raise

        provider, llm_calls = provider_delta(
            before_by_provider,
            updated.llm_calls_by_provider,
        )
        output = _without_branch_accumulators(dataclasses.asdict(updated))
        complete_agent_run(
            run,
            detail=_agent_run_detail(agent.name, output),
            provider=provider,
            llm_calls=llm_calls,
        )
        return output

    return node_fn


def _section_writer_node(state: dict[str, Any]) -> dict[str, Any]:
    from apps.agents.section_writer import SectionWriterAgent
    from apps.jobs.progress import complete_agent_run, fail_agent_run, start_agent_run
    from apps.pipeline.state import PipelineState, SectionWriteTask

    task_data = state.get("write_task", {})
    task = SectionWriteTask(**task_data)
    ps = PipelineState.from_dict(state)
    run = start_agent_run(
        ps.job_id,
        "section_writer",
        {
            "section_id": task.section_id,
            "section_kind": task.section_kind,
            "heading": task.heading,
            "revision_count": task.revision_count,
        },
    )
    try:
        draft, usage_delta = SectionWriterAgent().run_task(ps, task)
    except Exception as exc:
        fail_agent_run(run, exc)
        raise

    output = {
        "section_drafts": [dataclasses.asdict(draft)],
        "section_usage_deltas": [usage_delta],
    }
    complete_agent_run(
        run,
        detail=_agent_run_detail("section_writer", output),
        provider=usage_delta.get("provider", ""),
        llm_calls=int(usage_delta.get("calls", 0) or 0),
    )
    return output


def _join_draft_node(state: dict[str, Any]) -> dict[str, Any]:
    from apps.agents.join_draft import JoinDraftAgent
    from apps.jobs.progress import complete_agent_run, fail_agent_run, start_agent_run
    from apps.pipeline.state import PipelineState

    ps = PipelineState.from_dict(state)
    run = start_agent_run(ps.job_id, "join_draft", {"revision_count": ps.revision_count})
    try:
        updated = JoinDraftAgent().run(ps)
    except Exception as exc:
        fail_agent_run(run, exc)
        raise
    output = _without_branch_accumulators(dataclasses.asdict(updated))
    complete_agent_run(run, detail=_agent_run_detail("join_draft", output))
    return output


def _coordinator_router_node(state: dict[str, Any]) -> dict[str, Any]:
    from apps.agents.coordinator import CoordinatorAgent
    from apps.jobs.progress import complete_agent_run, fail_agent_run, start_agent_run
    from apps.pipeline.state import PipelineState

    ps = PipelineState.from_dict(state)
    run = start_agent_run(
        ps.job_id,
        "coordinator_router",
        {
            "after": ps.current_agent,
            "revision_count": ps.revision_count,
        },
    )
    try:
        updated = CoordinatorAgent().run_router(ps)
    except Exception as exc:
        fail_agent_run(run, exc)
        raise
    output = _without_branch_accumulators(dataclasses.asdict(updated))
    complete_agent_run(run, detail=_agent_run_detail("coordinator_router", output))
    return output


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
