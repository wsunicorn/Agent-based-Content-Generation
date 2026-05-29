"""
QA Agent scores the final content on 6 dimensions.

Token optimisation:
  - Completeness (15 pts) and SEO (15 pts) are computed with pure Python.
  - One LLM call scores clarity (20), accuracy (20), engagement (15), and format (15).
  - Pass threshold: 75 / 100.
"""
from __future__ import annotations

import logging

from django.conf import settings
from pydantic import BaseModel, Field

from apps.pipeline.state import PipelineState, QAReport

from .base import BaseAgent
from .content_guides import get_content_type_guide, get_required_elements
from .domain_guides import get_domain_guide_text
from .image_research import markdown_for_image

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 75.0


class QAScores(BaseModel):
    clarity_score: float = Field(ge=0, le=20, description="Clarity and readability (0-20)")
    accuracy_score: float = Field(ge=0, le=20, description="Factual accuracy (0-20)")
    engagement_score: float = Field(ge=0, le=15, description="Reader engagement (0-15)")
    format_adherence_score: float = Field(ge=0, le=15, description="Content type format adherence (0-15)")
    feedback: list[str] = Field(default_factory=list, description="Actionable feedback items")
    decision: str = Field(default="review", description="approve, revise, or fail_with_warning")
    next_action: str = Field(default="revise_editor")
    target_agent: str = Field(default="editor")
    target_section_ids: list[int] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    revision_instructions: str = Field(default="")


class QAAgent(BaseAgent):
    name = "qa"
    temperature = 0.2

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[QAAgent] Scoring content")
        state.current_agent = self.name

        text = self._ensure_image_assets(state.edited_draft or state.draft, state)
        if not text:
            logger.warning("[QAAgent] No content to score")
            return state

        # Pure-Python scores (zero LLM cost)
        completeness = self._completeness_score(state)        # max 15
        seo_pts = self._seo_score_pts(state)                  # max 15

        if state.quality_mode == "fast" and not getattr(settings, "FAST_MODE_LLM_QA", False):
            llm_scores = self._fast_llm_scores(state, text)
        else:
            # LLM scores (1 call)
            llm_scores = self._llm_score(state, text)
            self._track_usage(state, calls=1)

        total = (
            llm_scores.clarity_score
            + llm_scores.accuracy_score
            + llm_scores.engagement_score
            + llm_scores.format_adherence_score
            + seo_pts
            + completeness
        )

        report = QAReport(
            overall_score=round(total, 1),
            clarity_score=llm_scores.clarity_score,
            accuracy_score=llm_scores.accuracy_score,
            engagement_score=llm_scores.engagement_score,
            format_adherence_score=llm_scores.format_adherence_score,
            seo_score=seo_pts,
            completeness_score=completeness,
            passed=total >= PASS_THRESHOLD,
            feedback=llm_scores.feedback,
            decision=llm_scores.decision,
            next_action=llm_scores.next_action,
            target_agent=llm_scores.target_agent,
            target_section_ids=llm_scores.target_section_ids,
            issues=llm_scores.issues or llm_scores.feedback,
            revision_instructions=llm_scores.revision_instructions,
        )
        self._normalise_routing(state, report)
        state.qa_report = report

        if report.passed:
            state.final_content = text
            state.edited_draft = text
            state.completed = True
            logger.info("[QAAgent] PASSED with score %.1f", total)
        else:
            state.completed = False
            logger.info("[QAAgent] FAILED with score %.1f — needs revision", total)

        return state

    @staticmethod
    def _ensure_image_assets(text: str, state: PipelineState) -> str:
        """Reinsert auto-selected images if an editor model accidentally removed them."""
        if not text or not state.image_assets:
            return text

        missing = [asset for asset in state.image_assets if asset.url and asset.url not in text]
        if not missing:
            return text

        blocks = "\n\n".join(markdown_for_image(asset) for asset in missing)
        return f"{text.rstrip()}\n\n## Visual References\n\n{blocks}".strip()

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

    def _fast_llm_scores(self, state: PipelineState, text: str) -> QAScores:
        word_count = len(text.split())
        target = max(1, state.target_length)
        length_ratio = min(1.2, word_count / target)
        clarity = 18.0 if word_count >= 80 else 13.0
        accuracy = 18.0 if state.fact_check_passed else 13.0
        engagement = 13.0 if length_ratio >= 0.65 else 9.0
        format_adherence = self._format_heuristic_score(state, text)
        feedback = []
        if length_ratio < 0.65:
            feedback.append("Draft is shorter than expected.")
        if not state.fact_check_passed:
            feedback.append("Fact-check warnings remain.")
        return QAScores(
            clarity_score=clarity,
            accuracy_score=accuracy,
            engagement_score=engagement,
            format_adherence_score=format_adherence,
            feedback=feedback or ["Fast QA heuristic passed."],
            decision="approve",
            next_action="approve",
            target_agent="",
            issues=[],
            revision_instructions="",
        )

    def _format_heuristic_score(self, state: PipelineState, text: str) -> float:
        """Cheap fallback score for template shape when LLM QA is disabled."""
        lower = text.lower()
        score = 6.0

        heading_count = lower.count("\n## ")
        if heading_count >= max(2, min(4, len(state.sections))):
            score += 3.0

        for element in get_required_elements(state.content_type):
            words = [part for part in element.lower().replace("/", " ").split() if len(part) >= 4]
            if any(word in lower for word in words):
                score += 1.25

        if state.content_type == "tutorial" and any(marker in lower for marker in ["step", "bước", "prerequisite", "điều kiện"]):
            score += 2.0
        elif state.content_type == "technical_report" and any(marker in lower for marker in ["method", "scope", "finding", "limitation", "phạm vi", "hạn chế"]):
            score += 2.0
        elif state.content_type == "news_article" and any(marker in lower for marker in ["according", "said", "impact", "cho biết", "theo"]):
            score += 2.0
        elif state.content_type == "blog_post" and any(marker in lower for marker in ["example", "takeaway", "ví dụ", "bài học"]):
            score += 2.0

        return min(15.0, round(score, 1))

    def _llm_score(self, state: PipelineState, text: str) -> QAScores:
        system_prompt = (
            "You are a quality assurance reviewer for content. Score the article "
            "on four dimensions (use exact numeric scores within the valid ranges):\n"
            "- clarity_score: 0-20 (readability, sentence structure, logical flow)\n"
            "- accuracy_score: 0-20 (factual correctness, no contradictions)\n"
            "- engagement_score: 0-15 (hook, usefulness, reader momentum)\n"
            "- format_adherence_score: 0-15 (fit with the requested content type template)\n"
            "Also provide 2-5 concise actionable feedback items and routing instructions.\n"
            "Allowed next_action values: approve, redo_research, redo_outline, "
            "rewrite_section, revise_editor, redo_fact_check, redo_seo, fail_with_warning.\n"
            "Use rewrite_section only when specific sections are weak; then include "
            "target_section_ids from the provided section map."
        )

        snippet = text[:2000]
        section_map = self._section_map(state)
        user_prompt = (
            f"Topic: {state.topic}\n"
            f"Content type: {state.content_type.replace('_', ' ').title()}\n"
            f"Domain: {state.domain}\n"
            f"Audience: {state.audience or 'general'}\n"
            f"Tone: {state.tone or 'clear'}\n"
            f"Word count: {state.word_count} / {state.target_length} target\n\n"
            f"Section map:\n{section_map}\n\n"
            f"Content type guide:\n{get_content_type_guide(state.content_type)}\n\n"
            f"Domain guide:\n{get_domain_guide_text(state.domain, state.audience, state.tone)}\n\n"
            f"Additional instructions:\n{state.additional_instructions or 'None'}\n\n"
            f"ARTICLE:\n{snippet}\n\n"
            "Score the article."
        )

        result = self._call_llm(system_prompt, user_prompt, output_schema=QAScores)

        if isinstance(result, QAScores):
            return result

        return QAScores(
            clarity_score=12.0,
            accuracy_score=12.0,
            engagement_score=8.0,
            format_adherence_score=8.0,
            feedback=["Unable to parse QA scores — using defaults."],
            decision="revise",
            next_action="revise_editor",
            target_agent="editor",
            issues=["Unable to parse QA scores."],
            revision_instructions="Review the draft for clarity, accuracy, and engagement.",
        )

    # ------------------------------------------------------------------ #
    # Routing helpers
    # ------------------------------------------------------------------ #

    def _normalise_routing(self, state: PipelineState, report: QAReport) -> None:
        allowed = {
            "approve": "",
            "redo_research": "research",
            "redo_outline": "outline",
            "rewrite_section": "writer",
            "revise_editor": "editor",
            "redo_fact_check": "fact_checker",
            "redo_seo": "seo",
            "fail_with_warning": "",
        }

        if report.passed:
            report.decision = "approve"
            report.next_action = "approve"
            report.target_agent = ""
            report.target_section_ids = []
            report.issues = report.issues or []
            return

        weak_sections = self._weak_section_ids(state)
        if weak_sections:
            report.next_action = "rewrite_section"
            report.target_agent = "writer"
            report.target_section_ids = weak_sections
            report.decision = "revise"
            report.issues = report.issues or ["One or more sections are underdeveloped."]
            report.revision_instructions = (
                report.revision_instructions
                or "Rewrite the targeted sections with more complete, useful content."
            )
            return

        if report.completeness_score < 10:
            report.next_action = "rewrite_section"
            report.target_agent = "writer"
            report.target_section_ids = []
            report.decision = "revise"
        elif report.format_adherence_score < 8:
            report.next_action = "redo_outline"
            report.target_agent = "outline"
            report.decision = "revise"
        elif report.format_adherence_score < 11:
            report.next_action = "revise_editor"
            report.target_agent = "editor"
            report.decision = "revise"
        elif report.seo_score < 10:
            report.next_action = "redo_seo"
            report.target_agent = "seo"
            report.decision = "revise"
        elif report.accuracy_score < 12 or len(state.unverified_claims) >= 5:
            report.next_action = "redo_fact_check"
            report.target_agent = "fact_checker"
            report.decision = "revise"
        elif report.clarity_score < 12 or report.engagement_score < 9:
            report.next_action = "revise_editor"
            report.target_agent = "editor"
            report.decision = "revise"
        else:
            report.next_action = report.next_action if report.next_action in allowed else "revise_editor"
            report.target_agent = allowed[report.next_action]
            report.decision = "revise"

        if report.next_action not in allowed:
            report.next_action = "revise_editor"
            report.target_agent = "editor"

        report.issues = report.issues or report.feedback or ["QA score below pass threshold."]
        report.revision_instructions = (
            report.revision_instructions
            or "Address the QA feedback and preserve the article structure."
        )

    @staticmethod
    def _section_map(state: PipelineState) -> str:
        if not state.writer_tasks:
            return "No section map available."
        return "\n".join(
            f"- {task.section_id}: {task.section_kind} - {task.heading}"
            for task in state.writer_tasks
        )

    @staticmethod
    def _weak_section_ids(state: PipelineState) -> list[int]:
        if not state.writer_tasks or not state.section_drafts:
            return []

        targets = {task.section_id: task.target_words for task in state.writer_tasks}
        latest: dict[int, tuple[int, int]] = {}
        for draft in state.section_drafts:
            current = latest.get(draft.section_id)
            if current is None or draft.revision_count >= current[0]:
                latest[draft.section_id] = (draft.revision_count, draft.word_count)

        return [
            section_id
            for section_id, target_words in targets.items()
            if target_words and latest.get(section_id, (0, 0))[1] < target_words * 0.5
        ]
