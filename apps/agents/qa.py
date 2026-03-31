"""
QA Agent — scores the final content on 5 dimensions.

Token optimisation:
  • Completeness (15 pts) and SEO (15 pts) computed with pure Python.
  • Single LLM call for clarity (25), accuracy (25), engagement (20).
  • Pass threshold: 75 / 100.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from apps.pipeline.state import PipelineState, QAReport

from .base import BaseAgent

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 75.0


class QAScores(BaseModel):
    clarity_score: float = Field(ge=0, le=25, description="Clarity and readability (0-25)")
    accuracy_score: float = Field(ge=0, le=25, description="Factual accuracy (0-25)")
    engagement_score: float = Field(ge=0, le=20, description="Reader engagement (0-20)")
    feedback: list[str] = Field(default_factory=list, description="Actionable feedback items")


class QAAgent(BaseAgent):
    name = "qa"
    temperature = 0.2

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[QAAgent] Scoring content")
        state.current_agent = self.name

        text = state.edited_draft or state.draft
        if not text:
            logger.warning("[QAAgent] No content to score")
            return state

        # Pure-Python scores (zero LLM cost)
        completeness = self._completeness_score(state)        # max 15
        seo_pts = self._seo_score_pts(state)                  # max 15

        # LLM scores (1 call)
        llm_scores = self._llm_score(state, text)
        self._track_usage(state, calls=1)

        total = (
            llm_scores.clarity_score
            + llm_scores.accuracy_score
            + llm_scores.engagement_score
            + seo_pts
            + completeness
        )

        report = QAReport(
            overall_score=round(total, 1),
            clarity_score=llm_scores.clarity_score,
            accuracy_score=llm_scores.accuracy_score,
            engagement_score=llm_scores.engagement_score,
            seo_score=seo_pts,
            completeness_score=completeness,
            passed=total >= PASS_THRESHOLD,
            feedback=llm_scores.feedback,
        )
        state.qa_report = report

        if report.passed:
            state.final_content = text
            state.completed = True
            logger.info("[QAAgent] PASSED with score %.1f", total)
        else:
            state.completed = False
            logger.info("[QAAgent] FAILED with score %.1f — needs revision", total)

        return state

    # ------------------------------------------------------------------ #
    # Pure-Python scoring helpers
    # ------------------------------------------------------------------ #

    def _completeness_score(self, state: PipelineState) -> float:
        """15 pts: word count vs target."""
        if not state.target_length:
            return 15.0
        ratio = state.word_count / state.target_length
        if ratio >= 0.9:
            return 15.0
        if ratio >= 0.75:
            return 10.0
        if ratio >= 0.5:
            return 5.0
        return 0.0

    def _seo_score_pts(self, state: PipelineState) -> float:
        """15 pts based on SEO metadata quality (pure Python)."""
        pts = 0.0
        meta = state.seo_metadata
        if meta.meta_title and len(meta.meta_title) <= 65:
            pts += 5
        if meta.meta_description and len(meta.meta_description) <= 165:
            pts += 5
        if meta.slug:
            pts += 2
        if meta.focus_keyword:
            pts += 3
        return pts

    # ------------------------------------------------------------------ #
    # LLM quality scoring (1 call)
    # ------------------------------------------------------------------ #

    def _llm_score(self, state: PipelineState, text: str) -> QAScores:
        system_prompt = (
            "You are a quality assurance reviewer for content. Score the article "
            "on three dimensions (use exact numeric scores within the valid ranges):\n"
            "• clarity_score: 0-25 (readability, sentence structure, logical flow)\n"
            "• accuracy_score: 0-25 (factual correctness, no contradictions)\n"
            "• engagement_score: 0-20 (hook, compelling voice, call-to-action)\n"
            "Also provide 2-5 concise actionable feedback items."
        )

        snippet = text[:2000]
        user_prompt = (
            f"Topic: {state.topic}\n"
            f"Content type: {state.content_type.replace('_', ' ').title()}\n"
            f"Word count: {state.word_count} / {state.target_length} target\n\n"
            f"ARTICLE:\n{snippet}\n\n"
            "Score the article."
        )

        result = self._call_llm(system_prompt, user_prompt, output_schema=QAScores)

        if isinstance(result, QAScores):
            return result

        return QAScores(
            clarity_score=15.0,
            accuracy_score=15.0,
            engagement_score=10.0,
            feedback=["Unable to parse QA scores — using defaults."],
        )
