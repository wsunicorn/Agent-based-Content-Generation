"""Realtime progress helpers for pipeline jobs."""
from __future__ import annotations

import json
import logging
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)

SNAPSHOT_LIMIT = 4000


AGENT_TYPE_MAP = {
    "coordinator": "coordinator",
    "coordinator_router": "coordinator_router",
    "image_research": "image_research",
    "research": "research",
    "outline": "outline",
    "writer": "writer",
    "section_writer": "section_writer",
    "join_draft": "join_draft",
    "editor": "editor",
    "fact_checker": "fact_checker",
    "seo": "seo",
    "qa": "qa",
}


def push_progress(job_id: str, agent: str, status: str, detail: dict | None = None) -> None:
    """Send a progress event to the job's WebSocket channel group."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            msg = {"type": "job_progress", "agent": agent, "status": status}
            if detail is not None:
                msg["detail"] = detail
            async_to_sync(channel_layer.group_send)(f"job_{job_id}", msg)
    except Exception as exc:
        logger.debug("WebSocket progress push failed: %s", exc)


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
        logger.debug("WebSocket completion push failed: %s", exc)


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
        logger.debug("WebSocket error push failed: %s", exc)


def start_agent_run(job_id: str, agent: str, detail: dict | None = None):
    """Create a RUNNING AgentRun row so polling can reconstruct progress."""
    if not job_id:
        return None

    try:
        from apps.jobs.models import AgentRun

        agent_type = AGENT_TYPE_MAP.get(agent, "coordinator")
        attempt = (
            AgentRun.objects.filter(job_id=job_id, agent_type=agent_type).count() + 1
        )
        run = AgentRun.objects.create(
            job_id=job_id,
            agent_type=agent_type,
            status=AgentRun.Status.RUNNING,
            attempt=attempt,
            started_at=timezone.now(),
            prompt_snapshot=_snapshot(detail or {}),
        )
        push_progress(job_id, agent, "running", detail)
        return run
    except Exception as exc:
        logger.debug("Could not start AgentRun for %s/%s: %s", job_id, agent, exc)
        push_progress(job_id, agent, "running", detail)
        return None


def complete_agent_run(
    run,
    *,
    detail: dict | None = None,
    provider: str = "",
    llm_calls: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    if run is None:
        return

    try:
        from apps.jobs.models import AgentRun

        run.status = AgentRun.Status.COMPLETED
        run.completed_at = timezone.now()
        run.provider = provider or run.provider
        run.llm_calls_count = max(0, int(llm_calls or 0))
        run.input_tokens = max(0, int(input_tokens or 0))
        run.output_tokens = max(0, int(output_tokens or 0))
        run.response_snapshot = _snapshot(detail or {})
        run.save(
            update_fields=[
                "status",
                "completed_at",
                "provider",
                "llm_calls_count",
                "input_tokens",
                "output_tokens",
                "response_snapshot",
            ]
        )
    except Exception as exc:
        logger.debug("Could not complete AgentRun %s: %s", getattr(run, "id", None), exc)


def fail_agent_run(run, exc: Exception) -> None:
    if run is None:
        return

    try:
        from apps.jobs.models import AgentRun

        run.status = AgentRun.Status.FAILED
        run.completed_at = timezone.now()
        run.error_message = str(exc)[:2000]
        run.save(update_fields=["status", "completed_at", "error_message"])
    except Exception as save_exc:
        logger.debug("Could not fail AgentRun %s: %s", getattr(run, "id", None), save_exc)


def provider_delta(before: dict[str, int], after: dict[str, int]) -> tuple[str, int]:
    """Return the provider with the largest call delta and the total delta."""
    deltas = {
        provider: max(0, int(after.get(provider, 0)) - int(before.get(provider, 0)))
        for provider in set(before) | set(after)
    }
    total = sum(deltas.values())
    if not total:
        return "", 0
    provider = max(deltas, key=deltas.get)
    return provider, total


def _snapshot(data: Any) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        text = str(data)
    return text[:SNAPSHOT_LIMIT]
