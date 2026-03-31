"""
Writer Agent — produces introduction, body sections, and conclusion.

Token optimisation:
  • Introduction and conclusion each cost 1 LLM call.
  • Each body section is 1 LLM call (brief + key points passed, NOT full draft).
  • Total calls: 2 + len(sections) — typically 6-8 calls.
  • 6.5 s delay between calls is enforced by BaseAgent._call_llm.
"""
from __future__ import annotations

import logging

from apps.pipeline.state import PipelineState

from .base import BaseAgent

logger = logging.getLogger(__name__)

# Words allocated to each structural part
INTRO_WORDS = 150
CONCLUSION_WORDS = 150


class WriterAgent(BaseAgent):
    name = "writer"
    temperature = 0.8   # Slightly higher for more engaging prose

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[WriterAgent] Writing article: %s", state.topic[:80])
        state.current_agent = self.name

        words_per_section = self._words_per_section(state)

        # --- Introduction ---
        state.introduction = self._write_introduction(state)
        self._track_usage(state, calls=1)

        # --- Body sections ---
        state.body_sections = {}
        for section in state.sections:
            content = self._write_section(state, section, words_per_section)
            state.body_sections[section.heading] = content
            self._track_usage(state, calls=1)

        # --- Conclusion ---
        state.conclusion = self._write_conclusion(state)
        self._track_usage(state, calls=1)

        # Assemble full draft
        state.draft = self._assemble_draft(state)
        state.word_count = len(state.draft.split())

        logger.info(
            "[WriterAgent] Draft complete — %d words, %d sections",
            state.word_count,
            len(state.sections),
        )
        return state

    # ------------------------------------------------------------------ #
    # Word budget helper
    # ------------------------------------------------------------------ #

    def _words_per_section(self, state: PipelineState) -> int:
        body_budget = state.target_length - INTRO_WORDS - CONCLUSION_WORDS
        n = len(state.sections) or 1
        return max(150, body_budget // n)

    # ------------------------------------------------------------------ #
    # Introduction
    # ------------------------------------------------------------------ #

    def _write_introduction(self, state: PipelineState) -> str:
        system_prompt = (
            "You are an expert content writer. Write a compelling introduction "
            "that hooks the reader and presents the article's main thesis clearly."
        )
        keywords_str = ", ".join(state.keywords[:5]) if state.keywords else ""
        section_headings = [s.heading for s in state.sections]

        user_prompt = (
            f"Article topic: {state.topic}\n"
            f"Content type: {state.content_type.replace('_', ' ').title()}\n"
            f"Keywords to naturally include: {keywords_str or 'none'}\n"
            f"The article will cover: {', '.join(section_headings)}\n\n"
            f"Research context:\n{state.research_summary[:1000]}\n\n"
            f"Write a {INTRO_WORDS}-word introduction in Markdown."
        )
        return self._text(self._call_llm(system_prompt, user_prompt))

    # ------------------------------------------------------------------ #
    # Body section
    # ------------------------------------------------------------------ #

    def _write_section(self, state: PipelineState, section, words: int) -> str:
        system_prompt = (
            "You are an expert content writer. Write a focused, informative "
            "section for an article based on the provided brief and key points."
        )
        key_points_str = "\n".join(f"• {kp}" for kp in section.key_points)

        user_prompt = (
            f"Article topic: {state.topic}\n"
            f"Section heading: ## {section.heading}\n"
            f"Section brief: {section.brief}\n\n"
            f"Key points to cover:\n{key_points_str}\n\n"
            f"Research context:\n{state.research_summary[:800]}\n\n"
            f"Write approximately {words} words for this section in Markdown. "
            f"Do not repeat the heading — only write the body text."
        )
        return self._text(self._call_llm(system_prompt, user_prompt))

    # ------------------------------------------------------------------ #
    # Conclusion
    # ------------------------------------------------------------------ #

    def _write_conclusion(self, state: PipelineState) -> str:
        system_prompt = (
            "You are an expert content writer. Write a strong conclusion that "
            "summarises the key takeaways and ends with a clear call-to-action or insight."
        )
        covered = [s.heading for s in state.sections]

        user_prompt = (
            f"Article topic: {state.topic}\n"
            f"Sections covered: {', '.join(covered)}\n\n"
            f"Write a {CONCLUSION_WORDS}-word conclusion in Markdown."
        )
        return self._text(self._call_llm(system_prompt, user_prompt))

    # ------------------------------------------------------------------ #
    # Assemble markdown draft
    # ------------------------------------------------------------------ #

    def _assemble_draft(self, state: PipelineState) -> str:
        parts = []

        if state.introduction:
            parts.append(state.introduction)

        for section in state.sections:
            parts.append(f"\n## {section.heading}\n")
            body = state.body_sections.get(section.heading, "")
            if body:
                parts.append(body)

        if state.conclusion:
            parts.append("\n## Conclusion\n")
            parts.append(state.conclusion)

        return "\n\n".join(parts)
