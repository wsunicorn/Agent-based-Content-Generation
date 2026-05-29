"""
Celery tasks for the content pipeline.

run_pipeline(job_id) is the main entry point — it:
  1. Loads the Job record.
  2. Builds a PipelineState from it.
  3. Runs the LangGraph pipeline via graph.stream() (yields per-node output).
  4. Pushes progress updates over Django Channels WebSocket after each node.
  5. Saves artifacts (draft, SEO, QA report) and updates the Job status.
"""
from __future__ import annotations

import dataclasses
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket push helper
# ---------------------------------------------------------------------------

def push_progress(job_id: str, agent: str, status: str, detail: dict | None = None) -> None:
    """Send a progress event to the job's WebSocket channel group."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            msg = {"type": "job_progress", "agent": agent, "status": status}
            if detail:
                msg["detail"] = detail
            async_to_sync(channel_layer.group_send)(f"job_{job_id}", msg)
    except Exception as exc:
        logger.debug("WebSocket push failed (non-critical): %s", exc)


def push_completed(job_id: str, qa_score: float) -> None:
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"job_{job_id}",
                {"type": "job_completed", "qa_score": qa_score},
            )
    except Exception as exc:
        logger.debug("WebSocket push failed (non-critical): %s", exc)


def push_error(job_id: str, message: str) -> None:
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"job_{job_id}",
                {"type": "job_error", "message": message},
            )
    except Exception as exc:
        logger.debug("WebSocket push failed (non-critical): %s", exc)


def _initial_state_from_job(job):
    from apps.pipeline.quality import normalise_quality_mode, revision_limits
    from apps.pipeline.state import PipelineState

    lang = getattr(job, "language", "") or "English"
    base_instructions = job.additional_instructions or ""
    lang_prefix = (
        f"Language: Write the entire article in {lang}.\n"
        if lang and lang.lower() != "english"
        else ""
    )
    combined_instructions = (lang_prefix + base_instructions).strip()
    quality_mode = normalise_quality_mode(getattr(job, "quality_mode", "standard"))
    max_revisions, max_agent_retries = revision_limits(quality_mode)

    return PipelineState(
        job_id=str(job.id),
        topic=job.topic,
        content_type=job.content_type,
        domain=getattr(job, "domain", "tech") or "tech",
        audience=getattr(job, "audience", "") or "",
        tone=getattr(job, "tone", "") or "",
        quality_mode=quality_mode,
        target_length=job.target_length,
        keywords=job.keywords or [],
        language=lang,
        additional_instructions=combined_instructions,
        max_revisions=max_revisions,
        max_agent_retries=max_agent_retries,
    )


def _outline_sections_from_payload(payload):
    from apps.pipeline.state import OutlineSection

    sections = []
    for item in payload or []:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading") or "").strip()
        brief = str(item.get("brief") or "").strip()
        if not heading:
            continue
        key_points = item.get("key_points") or []
        if isinstance(key_points, str):
            key_points = [line.strip("- ").strip() for line in key_points.splitlines()]
        sections.append(
            OutlineSection(
                heading=heading[:180],
                level=int(item.get("level") or 1),
                brief=brief[:1000],
                key_points=[str(point).strip() for point in key_points if str(point).strip()][:8],
                template_role=str(item.get("template_role") or "").strip()[:120],
            )
        )
    return sections


# ---------------------------------------------------------------------------
# Main pipeline task
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0, ignore_result=False)
def run_pipeline(self, job_id: str):
    """Execute the full multi-agent pipeline for a job."""
    from apps.jobs.models import Job
    from apps.pipeline.graph import get_pipeline_graph
    from apps.pipeline.quality import normalise_quality_mode, revision_limits
    from apps.pipeline.state import PipelineState

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        logger.error("Job %s not found", job_id)
        return {"error": "Job not found"}

    # Mark job as running
    resume_from_outline = bool(
        job.pipeline_state
        and job.outline_approved_at
        and getattr(job, "approved_outline", None)
    )

    job.status = Job.Status.RUNNING
    update_fields = ["status"]
    if not job.started_at:
        job.started_at = dj_timezone.now()
        update_fields.append("started_at")
    job.save(update_fields=update_fields)

    # Build initial state — combine language preference into additional_instructions
    lang = getattr(job, "language", "") or "English"
    base_instructions = job.additional_instructions or ""
    lang_prefix = f"Language: Write the entire article in {lang}.\n" if lang and lang.lower() != "english" else ""
    combined_instructions = (lang_prefix + base_instructions).strip()
    quality_mode = normalise_quality_mode(getattr(job, "quality_mode", "standard"))
    max_revisions, max_agent_retries = revision_limits(quality_mode)

    state = PipelineState(
        job_id=str(job.id),
        topic=job.topic,
        content_type=job.content_type,
        domain=getattr(job, "domain", "tech") or "tech",
        audience=getattr(job, "audience", "") or "",
        tone=getattr(job, "tone", "") or "",
        quality_mode=quality_mode,
        target_length=job.target_length,
        keywords=job.keywords or [],
        language=lang,
        additional_instructions=combined_instructions,
        max_revisions=max_revisions,
        max_agent_retries=max_agent_retries,
    )
    if resume_from_outline:
        state = PipelineState.from_dict(job.pipeline_state)
        state.job_id = str(job.id)
        state.sections = _outline_sections_from_payload(job.approved_outline)
        state.outline_approved = True
        state.completed = False
        state.error = None

    try:
        graph = get_pipeline_graph()
        initial = dataclasses.asdict(state)
        final_state = dict(initial)

        # Use stream() so we can push WebSocket progress after each node
        stream_config = {
            "max_concurrency": max(1, getattr(settings, "MAX_PARALLEL_WRITERS", 2)),
            "recursion_limit": max(25, getattr(settings, "LANGGRAPH_RECURSION_LIMIT", 80)),
        }
        for chunk in graph.stream(initial, stream_config):
            for node_name, node_output in chunk.items():
                _merge_graph_output(final_state, node_output)
                _update_job_progress(job, final_state)
                # Build rich detail payload for the frontend
                detail: dict = {}
                if node_name == "research":
                    raw_sources = node_output.get("sources", [])
                    detail = {
                        "sources_count": len(raw_sources),
                        "sources": [
                            {"title": s.get("title", ""), "url": s.get("url", "")}
                            for s in raw_sources[:6]
                            if isinstance(s, dict)
                        ],
                    }
                elif node_name == "image_research":
                    image_assets = node_output.get("image_assets", []) or []
                    detail = {
                        "image_assets_count": len(image_assets),
                        "providers": sorted({
                            item.get("provider", "")
                            for item in image_assets
                            if isinstance(item, dict) and item.get("provider")
                        }),
                    }
                elif node_name == "outline":
                    sections = node_output.get("sections", [])
                    detail = {"sections_count": len(sections)}
                elif node_name == "writer":
                    tasks = node_output.get("writer_tasks", []) or []
                    detail = {"tasks_count": len(tasks)}
                elif node_name == "section_writer":
                    drafts = node_output.get("section_drafts", []) or []
                    draft = drafts[0] if drafts else {}
                    detail = {
                        "heading": draft.get("heading", ""),
                        "section_kind": draft.get("section_kind", ""),
                        "word_count": draft.get("word_count", 0),
                    }
                elif node_name == "join_draft":
                    draft = node_output.get("draft", "") or ""
                    detail = {"word_count": len(draft.split())}
                elif node_name == "editor":
                    edited = node_output.get("edited_draft", "") or ""
                    detail = {"word_count": len(edited.split())}
                elif node_name == "fact_checker":
                    report = node_output.get("fact_check_report") or {}
                    detail = {
                        "passed": node_output.get("fact_check_passed", False),
                        "unverified_count": len(node_output.get("unverified_claims", []) or []),
                        "claims_checked": report.get("claims_checked", 0),
                        "mode": report.get("mode", ""),
                    }
                elif node_name == "coordinator_router":
                    detail = {
                        "next_action": node_output.get("next_action", ""),
                        "target_agent": node_output.get("target_agent", ""),
                        "revision_count": node_output.get("revision_count", 0),
                        "issues": node_output.get("routing_issues", [])[:3],
                    }
                elif node_name == "seo":
                    metadata = node_output.get("seo_metadata") or {}
                    detail = {
                        "focus_keyword": metadata.get("focus_keyword", ""),
                        "seo_score": metadata.get("seo_score", 0),
                    }
                elif node_name == "qa":
                    qa = node_output.get("qa_report")
                    if isinstance(qa, dict):
                        detail = {
                            "qa_score": qa.get("overall_score", 0),
                            "format_adherence_score": qa.get("format_adherence_score", 0),
                            "next_action": qa.get("next_action", ""),
                        }
                push_progress(job_id, node_name, "completed", detail or None)
                logger.info("Node completed: %s (job=%s)", node_name, job_id)
                if (
                    node_name == "outline"
                    and job.outline_review_required
                    and not resume_from_outline
                ):
                    paused_state = PipelineState.from_dict(final_state)
                    job.pipeline_state = dataclasses.asdict(paused_state)
                    job.status = Job.Status.PAUSED
                    job.save(update_fields=["pipeline_state", "status"])
                    _save_outline_checkpoint_artifacts(job, paused_state)
                    push_progress(
                        job_id,
                        "outline_review",
                        "paused",
                        {
                            "sections_count": len(paused_state.sections),
                            "message": "Outline ready for approval.",
                        },
                    )
                    logger.info("Job %s paused for outline review", job_id)
                    return {"status": "paused", "job_id": job_id}

        # Reconstruct PipelineState from final dict
        state = PipelineState.from_dict(final_state)

        # Persist artifacts
        _save_artifacts(job, state)
        _save_revisions(job, state)

        # Update job record
        qa_score = state.qa_report.overall_score if state.qa_report else 0.0
        job.status = Job.Status.COMPLETED
        job.completed_at = dj_timezone.now()
        job.llm_calls_count = state.llm_calls_total
        job.llm_tokens_used = state.llm_tokens_total
        job.llm_usage_by_provider = _build_llm_usage_by_provider(state)
        job.pipeline_state = dataclasses.asdict(state)
        job.error_message = ""
        job.save(update_fields=[
            "status", "completed_at", "llm_calls_count",
            "llm_tokens_used", "llm_usage_by_provider", "pipeline_state", "error_message",
        ])

        push_completed(job_id, qa_score)
        logger.info(
            "Job %s completed — QA score=%.1f, LLM calls=%d",
            job_id, qa_score, state.llm_calls_total,
        )
        return {"status": "completed", "job_id": job_id}

    except Exception as exc:
        from apps.agents.base import GeminiDailyQuotaExceeded

        logger.exception("Job %s failed: %s", job_id, exc)
        job.status = Job.Status.FAILED

        if isinstance(exc, GeminiDailyQuotaExceeded):
            user_message = (
                "⛔ Gemini free-tier daily limit reached (20 req/day). "
                "Quota resets at midnight Pacific Time (~UTC-8). "
                "You can retry tomorrow or add billing at https://aistudio.google.com"
            )
        else:
            user_message = str(exc)

        job.error_message = user_message
        job.completed_at = dj_timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        push_error(job_id, user_message)
        raise


# ---------------------------------------------------------------------------
# Helper: persist pipeline outputs as Artifact records
# ---------------------------------------------------------------------------

def _next_artifact_version(job, artifact_type):
    from apps.jobs.models import Artifact

    latest = (
        Artifact.objects.filter(job=job, artifact_type=artifact_type)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
    )
    return int(latest or 0) + 1


def _save_outline_checkpoint_artifacts(job, state):
    from apps.jobs.models import Artifact

    artifacts_to_create = []

    if state.image_assets:
        artifact_type = Artifact.ArtifactType.IMAGE_ASSETS
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=artifact_type,
                content_json={"image_assets": [dataclasses.asdict(item) for item in state.image_assets]},
                version=_next_artifact_version(job, artifact_type),
            )
        )

    if state.research_summary:
        artifact_type = Artifact.ArtifactType.RESEARCH_SUMMARY
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=artifact_type,
                content_text=state.research_summary,
                content_json={"sources": [dataclasses.asdict(s) for s in state.sources]},
                word_count=len(state.research_summary.split()),
                version=_next_artifact_version(job, artifact_type),
            )
        )

    if state.sources:
        artifact_type = Artifact.ArtifactType.SOURCE_DOCUMENTS
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=artifact_type,
                content_json={"sources": [dataclasses.asdict(s) for s in state.sources]},
                word_count=sum(len(s.content.split()) for s in state.sources),
                version=_next_artifact_version(job, artifact_type),
            )
        )

    if state.sections:
        artifact_type = Artifact.ArtifactType.OUTLINE
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=artifact_type,
                content_json={"sections": [dataclasses.asdict(s) for s in state.sections]},
                version=_next_artifact_version(job, artifact_type),
            )
        )

    if artifacts_to_create:
        Artifact.objects.bulk_create(artifacts_to_create)


def _save_artifacts(job, state):
    from apps.jobs.models import Artifact

    artifacts_to_create = []

    if state.image_assets:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.IMAGE_ASSETS,
                content_json={"image_assets": [dataclasses.asdict(item) for item in state.image_assets]},
                word_count=0,
            )
        )

    if state.research_summary:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.RESEARCH_SUMMARY,
                content_text=state.research_summary,
                content_json={"sources": [dataclasses.asdict(s) for s in state.sources]},
                word_count=len(state.research_summary.split()),
            )
        )

    if state.sources:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.SOURCE_DOCUMENTS,
                content_json={"sources": [dataclasses.asdict(s) for s in state.sources]},
                word_count=sum(len(s.content.split()) for s in state.sources),
            )
        )

    if state.sections:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.OUTLINE,
                content_json={"sections": [dataclasses.asdict(s) for s in state.sections]},
            )
        )

    if state.draft:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.DRAFT,
                content_text=state.draft,
                word_count=len(state.draft.split()),
            )
        )

    if state.edited_draft:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.EDITED_DRAFT,
                content_text=state.edited_draft,
                word_count=len(state.edited_draft.split()),
            )
        )

    if state.final_content:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.FINAL_CONTENT,
                content_text=state.final_content,
                word_count=len(state.final_content.split()),
            )
        )

    if state.seo_metadata:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.SEO_METADATA,
                content_json=dataclasses.asdict(state.seo_metadata),
            )
        )

    if state.fact_check_report:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.FACT_CHECK_REPORT,
                content_json=state.fact_check_report,
            )
        )

    if state.qa_report:
        artifacts_to_create.append(
            Artifact(
                job=job,
                artifact_type=Artifact.ArtifactType.QA_REPORT,
                content_json=dataclasses.asdict(state.qa_report),
            )
        )

    if artifacts_to_create:
        Artifact.objects.bulk_create(artifacts_to_create)


def _save_revisions(job, state):
    from apps.jobs.models import AgentRun, Revision

    if not state.revision_events:
        return

    valid_agents = {choice[0] for choice in AgentRun.AgentType.choices}
    existing_numbers = set(
        Revision.objects.filter(job=job).values_list("revision_number", flat=True)
    )
    revisions_to_create = []

    for event in state.revision_events:
        revision_number = int(event.get("revision_number") or 0)
        if not revision_number or revision_number in existing_numbers:
            continue

        triggered_by = event.get("triggered_by") or "qa"
        if triggered_by == "coordinator_router":
            triggered_by = "coordinator"
        if triggered_by not in valid_agents:
            triggered_by = "qa"

        issues = event.get("issues") or []
        if event.get("target_section_ids"):
            issues = list(issues) + [
                f"Target section ids: {event.get('target_section_ids')}"
            ]
        if event.get("target_agent"):
            issues = list(issues) + [f"Target agent: {event.get('target_agent')}"]
        if event.get("next_action"):
            issues = list(issues) + [f"Next action: {event.get('next_action')}"]

        revisions_to_create.append(
            Revision(
                job=job,
                revision_number=revision_number,
                triggered_by=triggered_by,
                reason=event.get("reason") or "Revision requested by router.",
                issues=issues,
                resolved=True,
            )
        )
        existing_numbers.add(revision_number)

    if revisions_to_create:
        Revision.objects.bulk_create(revisions_to_create)


def _merge_graph_output(final_state: dict, node_output: dict) -> None:
    """Merge stream chunks using the same reducer semantics as the graph."""
    list_reducer_keys = {"section_drafts", "section_usage_deltas"}
    for key, value in node_output.items():
        if key in list_reducer_keys:
            final_state[key] = (final_state.get(key) or []) + (value or [])
        else:
            final_state[key] = value


def _update_job_progress(job, final_state: dict) -> None:
    """Persist partial usage while the graph is still running."""
    try:
        from apps.pipeline.state import PipelineState

        state = PipelineState.from_dict(final_state)
        job.llm_calls_count = state.llm_calls_total
        job.llm_tokens_used = state.llm_tokens_total
        job.llm_usage_by_provider = _build_llm_usage_by_provider(state)
        job.save(update_fields=[
            "llm_calls_count",
            "llm_tokens_used",
            "llm_usage_by_provider",
        ])
    except Exception as exc:
        logger.debug("Could not update partial job progress: %s", exc)


def _build_llm_usage_by_provider(state) -> dict:
    """Return provider-level usage in a shape that is easy to render and query."""
    providers = set(state.llm_calls_by_provider) | set(state.llm_tokens_by_provider)
    return {
        provider: {
            "calls": state.llm_calls_by_provider.get(provider, 0),
            "tokens": state.llm_tokens_by_provider.get(provider, 0),
        }
        for provider in sorted(providers)
    }
