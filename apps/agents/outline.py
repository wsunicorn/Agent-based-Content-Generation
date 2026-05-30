"""
Outline Agent — generates a structured article outline.

Token optimisation:
  • Only passes research_summary (not full source texts) to the LLM.
  • Returns structured JSON (sections list) parsed via Pydantic.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata

from pydantic import BaseModel, Field

from apps.pipeline.state import OutlineSection, PipelineState

from .base import BaseAgent
from .content_guides import get_content_type_guide, get_outline_blueprint
from .domain_guides import get_domain_guide_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema for structured LLM output
# ---------------------------------------------------------------------------

class SectionSchema(BaseModel):
    heading: str
    level: int = Field(default=1, ge=1, le=2)
    template_role: str = Field(default="", description="The content template role this section fulfills")
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
            f"Domain: {state.domain}\n"
            f"Audience: {state.audience or 'general'}\n"
            f"Tone: {state.tone or 'clear'}\n"
            f"Topic: {state.topic}\n"
            f"Target word count: {state.target_length} words\n"
            f"Keywords: {keywords_str}\n"
            f"Target sections: {target_sections}\n\n"
            f"Content type guide:\n{content_type_guide}\n\n"
            f"Domain guide:\n{get_domain_guide_text(state.domain, state.audience, state.tone)}\n\n"
            f"Outline blueprint:\n{get_outline_blueprint(state.content_type, target_sections)}\n\n"
            f"{self._listicle_instruction(state)}\n"
            f"Research summary:\n{state.research_summary}\n\n"
            f"Additional instructions: {state.additional_instructions or 'None'}\n\n"
            f"Generate exactly {target_sections} sections for the article body "
            "(exclude introduction and conclusion - those are separate). "
            "Each section must have a distinct template_role matching the blueprint, "
            "so different content types produce visibly different structures."
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
                    template_role=s.template_role,
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
                    template_role=s.get("template_role", ""),
                )
                for s in data
            ]
        except Exception as exc:
            logger.error("[OutlineAgent] Fallback parse failed: %s", exc)
            return []

    @staticmethod
    def _listicle_instruction(state: PipelineState) -> str:
        topic = _normalise_for_detection(state.topic)
        if not re.search(
            r"\btop\s*\d+|\btop\b|danh sach|xep hang|pho bien nhat|ua chuong nhat|"
            r"duoc ua chuong|best|most popular|ranked|ranking",
            topic,
        ):
            return ""

        count_match = re.search(r"\btop\s*(\d+)|\b(\d+)\s+", topic)
        requested_count = next((part for part in count_match.groups() if part), "") if count_match else ""
        count_text = requested_count or "all requested"
        return (
            "Listicle/ranking requirement:\n"
            f"- The topic asks for a ranked/list article. Do not narrow the outline to only one item.\n"
            f"- Include a body section whose explicit purpose is to cover the complete top {count_text} list.\n"
            "- Key points for that section must tell the writer to include every ranked item, not just examples.\n"
            "- Other body sections may cover selection criteria, comparison, how to choose, or takeaways.\n\n"
        )


def _normalise_for_detection(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).lower().strip()
