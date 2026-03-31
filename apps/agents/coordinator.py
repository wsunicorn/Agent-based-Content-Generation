"""
Coordinator Agent — initialises the pipeline state and validates inputs.

Responsibilities:
  • Validate and normalise job inputs.
  • Log the start of the pipeline.
  • Set initial PipelineState fields from the Job record.
"""
from __future__ import annotations

import logging

from apps.pipeline.state import PipelineState

from .base import BaseAgent

logger = logging.getLogger(__name__)

VALID_CONTENT_TYPES = {"blog_post", "technical_report", "news_article", "tutorial"}


class CoordinatorAgent(BaseAgent):
    name = "coordinator"

    def run(self, state: PipelineState) -> PipelineState:
        logger.info(
            "[CoordinatorAgent] Initialising pipeline — job_id=%s topic=%s",
            state.job_id,
            state.topic[:80],
        )
        state.current_agent = self.name

        # Normalise content type
        if state.content_type not in VALID_CONTENT_TYPES:
            state.content_type = "blog_post"

        # Clamp target length
        state.target_length = max(300, min(5000, state.target_length))

        # Sanitise keywords
        state.keywords = [kw.strip() for kw in state.keywords if kw.strip()][:10]

        logger.info(
            "[CoordinatorAgent] Pipeline configured — type=%s, target=%d words, keywords=%s",
            state.content_type,
            state.target_length,
            state.keywords,
        )
        # Coordinator does NOT make any LLM calls (saves 1 RPM slot)
        return state
