"""Quality-mode helpers for balancing speed and review depth."""
from __future__ import annotations

from django.conf import settings

VALID_QUALITY_MODES = {"fast", "standard", "strict"}


def normalise_quality_mode(value: str | None = None) -> str:
    mode = (value or getattr(settings, "PIPELINE_QUALITY_MODE", "standard") or "standard").lower()
    return mode if mode in VALID_QUALITY_MODES else "standard"


def revision_limits(mode: str | None = None) -> tuple[int, int]:
    """Return (max_revisions, max_agent_retries) for the chosen quality mode."""
    mode = normalise_quality_mode(mode)
    configured_revisions = max(0, getattr(settings, "MAX_PIPELINE_REVISIONS", 2))
    configured_agent_retries = max(0, getattr(settings, "MAX_AGENT_RETRIES", 1))

    if mode == "fast":
        return 0, 0
    if mode == "standard":
        return min(configured_revisions, 1), min(configured_agent_retries, 1)
    return configured_revisions, configured_agent_retries


def is_strict_fact_check(state) -> bool:
    mode = normalise_quality_mode(getattr(state, "quality_mode", "standard"))
    return mode == "strict" or getattr(state, "content_type", "") in {
        "technical_report",
        "news_article",
    }


def should_allow_fact_revision(state, unverified_count: int) -> bool:
    """Keep multi-agent review, but avoid expensive loops for soft content."""
    if unverified_count <= 0:
        return False

    mode = normalise_quality_mode(getattr(state, "quality_mode", "standard"))
    if mode == "fast":
        return False
    if is_strict_fact_check(state):
        return True

    # Standard blog/tutorial: revise only when the article has many hard claims.
    return unverified_count >= 4
