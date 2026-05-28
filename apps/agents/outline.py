"""
Outline Agent — generates a structured article outline.

Token optimisation:
  • Only passes research_summary (not full source texts) to the LLM.
  • Returns structured JSON (sections list) parsed via Pydantic.
"""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from apps.pipeline.state import OutlineSection, PipelineState

from .base import BaseAgent
from .content_guides import get_content_type_guide

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema for structured LLM output
# ---------------------------------------------------------------------------

class SectionSchema(BaseModel):
    heading: str
    level: int = Field(default=1, ge=1, le=2)
    brief: str
    key_points: list[str] = Field(default_factory=list)


class OutlineSchema(BaseModel):
    sections: list[SectionSchema]


# ---------------------------------------------------------------------------
# Content type → target section count
# ---------------------------------------------------------------------------
SECTION_COUNTS = {
    "blog_post": 4,
    "technical_report": 6,
    "news_article": 3,
    "tutorial": 5,
}


def _target_section_count(content_type: str, target_length: int, quality_mode: str = "standard") -> int:
    base = SECTION_COUNTS.get(content_type, 4)
    if quality_mode == "fast":
        if target_length <= 700:
            return 2
        return max(3, min(base, 4))
    if target_length <= 500:
        return 2
    if target_length <= 900:
        return max(3, min(base, 4))
    return base


class OutlineAgent(BaseAgent):
    name = "outline"

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[OutlineAgent] Generating outline for: %s", state.topic[:80])
        state.current_agent = self.name

        target_sections = _target_section_count(
            state.content_type,
            state.target_length,
            state.quality_mode,
        )
        content_type_guide = get_content_type_guide(state.content_type)

        system_prompt = (
            "You are a senior content strategist. Given a topic and research summary, "
            "create a well-structured article outline. Each section must have a clear "
            "heading, a 1-2 sentence brief for the writer, and 2-4 key points to cover. "
            "Make the structure visibly different for each content type."
        )

        keywords_str = ", ".join(state.keywords) if state.keywords else "none specified"
        user_prompt = (
            f"Content type: {state.content_type.replace('_', ' ').title()}\n"
            f"Topic: {state.topic}\n"
            f"Target word count: {state.target_length} words\n"
            f"Keywords: {keywords_str}\n"
            f"Target sections: {target_sections}\n\n"
            f"Content type guide:\n{content_type_guide}\n\n"
            f"Research summary:\n{state.research_summary}\n\n"
            f"Additional instructions: {state.additional_instructions or 'None'}\n\n"
            f"Generate {target_sections} sections for the article body "
            f"(exclude introduction and conclusion — those are separate)."
        )

        result = self._call_llm(system_prompt, user_prompt, output_schema=OutlineSchema)
        self._track_usage(state, calls=1)

        if isinstance(result, OutlineSchema):
            state.sections = [
                OutlineSection(
                    heading=s.heading,
                    level=s.level,
                    brief=s.brief,
                    key_points=s.key_points,
                )
                for s in result.sections
            ]
        else:
            # Fallback: parse raw text as JSON
            state.sections = self._parse_fallback(self._text(result))

        state.outline_approved = bool(state.sections)
        logger.info("[OutlineAgent] Generated %d sections", len(state.sections))
        return state

    # ------------------------------------------------------------------ #
    # Fallback JSON parser
    # ------------------------------------------------------------------ #

    def _parse_fallback(self, text: str) -> list[OutlineSection]:
        try:
            start = text.find("[")
            end = text.rfind("]") + 1
            data = json.loads(text[start:end])
            return [
                OutlineSection(
                    heading=s.get("heading", "Section"),
                    level=s.get("level", 1),
                    brief=s.get("brief", ""),
                    key_points=s.get("key_points", []),
                )
                for s in data
            ]
        except Exception as exc:
            logger.error("[OutlineAgent] Fallback parse failed: %s", exc)
            return []
