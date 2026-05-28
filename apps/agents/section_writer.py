"""Section writer agent used by LangGraph fan-out."""
from __future__ import annotations

import logging

from apps.pipeline.state import PipelineState, SectionDraft, SectionWriteTask

from .base import BaseAgent
from .content_guides import get_content_type_guide

logger = logging.getLogger(__name__)


class SectionWriterAgent(BaseAgent):
    name = "section_writer"
    temperature = 0.8

    def run(self, state: PipelineState) -> PipelineState:
        """Section writers are invoked with explicit tasks by the graph."""
        return state

    def run_task(self, state: PipelineState, task: SectionWriteTask) -> tuple[SectionDraft, dict]:
        logger.info(
            "[SectionWriterAgent] Writing %s #%d: %s",
            task.section_kind,
            task.section_id,
            task.heading[:80],
        )

        response = self._call_llm(
            self._system_prompt(task),
            self._user_prompt(state, task),
        )
        content = self._clean_content(self._text(response), task)
        word_count = len(content.split())

        draft = SectionDraft(
            section_id=task.section_id,
            section_kind=task.section_kind,
            heading=task.heading,
            content=content,
            word_count=word_count,
            revision_count=task.revision_count,
        )
        usage_delta = {
            "revision_count": task.revision_count,
            "provider": getattr(self, "_last_provider_name", "unknown"),
            "calls": 1,
            "tokens": 0,
        }
        return draft, usage_delta

    @staticmethod
    def _system_prompt(task: SectionWriteTask) -> str:
        if task.section_kind == "introduction":
            return (
                "You are an expert introduction writer. Write a concise article opening "
                "that hooks the reader, frames the problem, and previews the value. "
                "Do not add a Markdown heading."
            )
        if task.section_kind == "conclusion":
            return (
                "You are an expert conclusion writer. Write a concise ending that "
                "matches the content type and gives the reader a clear final takeaway. "
                "Do not add a Markdown heading."
            )
        return (
            "You are an expert section writer. Write one focused, useful article "
            "section from the provided brief. Do not repeat the Markdown heading."
        )

    def _user_prompt(self, state: PipelineState, task: SectionWriteTask) -> str:
        key_points = "\n".join(f"- {point}" for point in task.key_points) or "- None"
        source_notes = self._format_sources(task)
        revision_notes = (
            state.revision_instructions
            if state.revision_count > 0 and state.revision_instructions
            else "None"
        )

        return (
            f"Article topic: {state.topic}\n"
            f"Content type: {state.content_type.replace('_', ' ').title()}\n"
            f"Section kind: {task.section_kind}\n"
            f"Section heading: {task.heading}\n"
            f"Section brief: {task.brief}\n"
            f"Target length: approximately {task.target_words} words\n"
            f"Keywords: {', '.join(state.keywords) if state.keywords else 'none'}\n\n"
            f"Key points:\n{key_points}\n\n"
            f"Content type guide:\n{get_content_type_guide(state.content_type)}\n\n"
            f"Additional instructions:\n{state.additional_instructions or 'None'}\n\n"
            f"Revision instructions:\n{revision_notes}\n\n"
            f"Research summary:\n{state.research_summary[:900] or 'No external research summary available.'}\n\n"
            f"Relevant sources:\n{source_notes}\n\n"
            "Write only this section's content in Markdown."
        )

    @staticmethod
    def _format_sources(task: SectionWriteTask) -> str:
        if not task.relevant_sources:
            return "No source snippets available."
        lines = []
        for idx, source in enumerate(task.relevant_sources, start=1):
            lines.append(
                f"{idx}. {source.get('title', 'Untitled')} - {source.get('url', '')}\n"
                f"   {source.get('content', '')[:500]}"
            )
        return "\n".join(lines)

    @staticmethod
    def _clean_content(text: str, task: SectionWriteTask) -> str:
        cleaned = text.strip()
        heading_prefixes = [
            f"# {task.heading}",
            f"## {task.heading}",
            f"### {task.heading}",
        ]
        for prefix in heading_prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].lstrip()
                break
        return cleaned
