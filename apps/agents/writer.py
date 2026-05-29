"""Writer planner agent.

This node does not call an LLM. It turns the approved outline into independent
section-writing tasks so LangGraph can fan out to real section writer agents.
"""
from __future__ import annotations

import logging

from apps.pipeline.state import PipelineState, SectionWriteTask

from .base import BaseAgent
from .content_guides import get_conclusion_brief, get_conclusion_heading, get_intro_brief, get_intro_heading

logger = logging.getLogger(__name__)

INTRO_WORDS = 150
CONCLUSION_WORDS = 150
MIN_SECTION_WORDS = 70


class WriterAgent(BaseAgent):
    name = "writer"

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[WriterAgent] Planning section writers for: %s", state.topic[:80])
        state.current_agent = self.name

        intro_words = self._intro_words(state)
        body_words = self._words_per_section(state)
        conclusion_words = self._conclusion_words(state)

        tasks: list[SectionWriteTask] = [
            SectionWriteTask(
                section_id=0,
                section_kind="introduction",
                heading=get_intro_heading(state.content_type) or "Introduction",
                brief=get_intro_brief(state.content_type),
                template_role="Introduction",
                target_words=intro_words,
                relevant_sources=self._source_refs(state),
                revision_count=state.revision_count,
            )
        ]

        for idx, section in enumerate(state.sections, start=1):
            tasks.append(
                SectionWriteTask(
                    section_id=idx,
                    section_kind="body",
                    heading=section.heading,
                    brief=section.brief,
                    key_points=section.key_points,
                    template_role=section.template_role,
                    target_words=body_words,
                    relevant_sources=self._source_refs(state),
                    revision_count=state.revision_count,
                )
            )

        tasks.append(
            SectionWriteTask(
                section_id=len(tasks),
                section_kind="conclusion",
                heading=get_conclusion_heading(state.content_type),
                brief=get_conclusion_brief(state.content_type),
                template_role="Conclusion",
                target_words=conclusion_words,
                relevant_sources=self._source_refs(state, limit=2),
                revision_count=state.revision_count,
            )
        )

        state.writer_tasks = tasks
        state.needs_revision = False
        state.revision_reason = ""
        state.introduction = ""
        state.body_sections = {}
        state.conclusion = ""
        state.draft = ""
        state.edited_draft = ""
        state.final_content = ""
        state.word_count = 0

        logger.info("[WriterAgent] Planned %d section writer task(s)", len(tasks))
        return state

    def _intro_words(self, state: PipelineState) -> int:
        return min(INTRO_WORDS, max(60, int(state.target_length * 0.18)))

    def _conclusion_words(self, state: PipelineState) -> int:
        return min(CONCLUSION_WORDS, max(60, int(state.target_length * 0.14)))

    def _words_per_section(self, state: PipelineState) -> int:
        body_budget = state.target_length - self._intro_words(state) - self._conclusion_words(state)
        n = len(state.sections) or 1
        return max(MIN_SECTION_WORDS, body_budget // n)

    @staticmethod
    def _source_refs(state: PipelineState, limit: int = 3) -> list[dict[str, str]]:
        return [
            {
                "title": source.title,
                "url": source.url,
                "content": source.content[:500],
            }
            for source in state.sources[:limit]
        ]
