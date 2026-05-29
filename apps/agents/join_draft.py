"""Join section drafts into a single article draft."""
from __future__ import annotations

import logging

from apps.pipeline.state import PipelineState, SectionDraft

from .base import BaseAgent
from .content_guides import get_conclusion_heading, get_intro_heading
from .image_research import markdown_for_image

logger = logging.getLogger(__name__)


class JoinDraftAgent(BaseAgent):
    name = "join_draft"

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[JoinDraftAgent] Joining section drafts")
        state.current_agent = self.name

        drafts = self._current_revision_drafts(state)
        if not drafts:
            logger.warning("[JoinDraftAgent] No section drafts found for revision %d", state.revision_count)
            return state

        state.introduction = self._first_content(drafts, "introduction")
        state.body_sections = {
            draft.heading: draft.content
            for draft in drafts
            if draft.section_kind == "body"
        }
        state.conclusion = self._first_content(drafts, "conclusion")
        state.draft = self._assemble_draft(state)
        state.word_count = len(state.draft.split())

        self._apply_writer_usage(state)

        logger.info(
            "[JoinDraftAgent] Draft joined — %d words from %d section draft(s)",
            state.word_count,
            len(drafts),
        )
        return state

    def _current_revision_drafts(self, state: PipelineState) -> list[SectionDraft]:
        latest_by_section: dict[int, SectionDraft] = {}
        for draft in state.section_drafts:
            if draft.revision_count > state.revision_count:
                continue
            current = latest_by_section.get(draft.section_id)
            if current is None or draft.revision_count >= current.revision_count:
                latest_by_section[draft.section_id] = draft

        return sorted(latest_by_section.values(), key=lambda draft: draft.section_id)

    @staticmethod
    def _first_content(drafts: list[SectionDraft], section_kind: str) -> str:
        for draft in drafts:
            if draft.section_kind == section_kind:
                return draft.content
        return ""

    def _assemble_draft(self, state: PipelineState) -> str:
        parts = []

        if state.introduction:
            intro_heading = get_intro_heading(state.content_type)
            if intro_heading:
                parts.append(f"## {intro_heading}\n\n{state.introduction}")
            else:
                parts.append(state.introduction)
            image = self._image_block(state, 0)
            if image:
                parts.append(image)

        for idx, section in enumerate(state.sections, start=1):
            body = state.body_sections.get(section.heading, "")
            if body:
                parts.append(f"\n## {section.heading}\n\n{body}")
                image = self._image_block(state, idx)
                if image:
                    parts.append(image)

        if state.conclusion:
            parts.append(f"\n## {get_conclusion_heading(state.content_type)}\n\n{state.conclusion}")

        return "\n\n".join(part.strip() for part in parts if part.strip())

    @staticmethod
    def _image_block(state: PipelineState, index: int) -> str:
        if index >= len(state.image_assets):
            return ""
        return markdown_for_image(state.image_assets[index])

    @staticmethod
    def _apply_writer_usage(state: PipelineState) -> None:
        deltas = [
            delta
            for delta in state.section_usage_deltas
            if delta.get("revision_count") == state.revision_count
        ]
        for delta in deltas:
            calls = int(delta.get("calls", 0))
            tokens = int(delta.get("tokens", 0))
            provider = delta.get("provider", "unknown")
            state.llm_calls_total += calls
            state.llm_tokens_total += tokens
            state.llm_calls_by_provider[provider] = (
                state.llm_calls_by_provider.get(provider, 0) + calls
            )
            state.llm_tokens_by_provider[provider] = (
                state.llm_tokens_by_provider.get(provider, 0) + tokens
            )
