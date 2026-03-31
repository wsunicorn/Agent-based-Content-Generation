"""
Editor Agent — reviews and improves the draft.

Token optimisation:
  • Sends the full draft but requests ONLY a list of specific changes + revised text.
  • Single LLM call (not iterative per-paragraph).
  • Flags whether revision is truly needed (avoids writer loop).

NOTE: We deliberately avoid with_structured_output() for this agent because
embedding a long article as a JSON string field causes truncation on long content.
Instead, we use a tagged-section format that lets the LLM write the full draft
as plain text after a sentinel marker.
"""
from __future__ import annotations

import logging
import re

from apps.pipeline.state import PipelineState

from .base import BaseAgent

logger = logging.getLogger(__name__)

_CHANGES_MARKER = "## CHANGES"
_DRAFT_MARKER = "## REVISED_DRAFT"
_REWRITE_MARKER = "## NEEDS_REWRITE"


class EditorAgent(BaseAgent):
    name = "editor"
    temperature = 0.3   # Lower temp for more consistent editing

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[EditorAgent] Editing draft (%d words)", state.word_count)
        state.current_agent = self.name

        draft = state.edited_draft if state.edited_draft else state.draft
        if not draft:
            logger.warning("[EditorAgent] No draft to edit — skipping")
            return state

        system_prompt = (
            "You are a senior editor. Review and improve the provided draft for: "
            "clarity, flow, grammar, factual consistency, and adherence to the article "
            "brief. Make targeted improvements.\n\n"
            "Respond using EXACTLY these three sections in order:\n\n"
            f"{_CHANGES_MARKER}\n"
            "- bullet point for each significant change you made\n\n"
            f"{_DRAFT_MARKER}\n"
            "[the complete revised article in Markdown — do NOT truncate]\n\n"
            f"{_REWRITE_MARKER}\n"
            "NO  (or YES: <reason> if the draft needs a complete rewrite by the Writer)"
        )

        user_prompt = (
            f"Article topic: {state.topic}\n"
            f"Content type: {state.content_type.replace('_', ' ').title()}\n"
            f"Target length: {state.target_length} words\n"
            f"Keywords: {', '.join(state.keywords) if state.keywords else 'none'}\n\n"
            f"DRAFT TO EDIT:\n{draft}"
        )

        raw = self._call_llm(system_prompt, user_prompt)
        self._track_usage(state, calls=1)

        text = self._text(raw)
        revised_draft, changes_made, needs_revision, revision_reason = (
            self._parse_response(text, draft)
        )

        state.edited_draft = revised_draft
        state.editor_changes = changes_made
        state.needs_revision = needs_revision
        state.revision_reason = revision_reason
        if needs_revision:
            state.revision_count += 1

        state.word_count = len(state.edited_draft.split())
        logger.info(
            "[EditorAgent] Done — %d words, needs_revision=%s",
            state.word_count,
            state.needs_revision,
        )
        return state

    # ------------------------------------------------------------------
    # Response parser
    # ------------------------------------------------------------------

    def _parse_response(
        self, text: str, original_draft: str
    ) -> tuple[str, list[str], bool, str]:
        """
        Extract revised_draft, changes, needs_revision and revision_reason
        from the tagged-section response format.
        Falls back gracefully if the model doesn't follow the format exactly.
        """
        draft_idx = text.find(_DRAFT_MARKER)
        changes_idx = text.find(_CHANGES_MARKER)
        rewrite_idx = text.find(_REWRITE_MARKER)

        # --- revised draft -------------------------------------------------
        if draft_idx != -1:
            draft_start = draft_idx + len(_DRAFT_MARKER)
            draft_end = rewrite_idx if rewrite_idx > draft_idx else len(text)
            revised_draft = text[draft_start:draft_end].strip()
        else:
            # Model ignored markers — fall back to the full response as draft
            logger.warning(
                "[EditorAgent] %s marker not found; using full response as draft",
                _DRAFT_MARKER,
            )
            revised_draft = text.strip()

        # Sanity check: if we got less than 50% of the original, keep original
        if len(revised_draft.split()) < len(original_draft.split()) * 0.5:
            logger.warning(
                "[EditorAgent] Revised draft suspiciously short (%d vs %d words) — "
                "keeping original draft",
                len(revised_draft.split()),
                len(original_draft.split()),
            )
            revised_draft = original_draft

        # --- changes made --------------------------------------------------
        changes_made: list[str] = []
        if changes_idx != -1:
            changes_end = draft_idx if draft_idx > changes_idx else len(text)
            changes_block = text[changes_idx + len(_CHANGES_MARKER):changes_end]
            for line in changes_block.splitlines():
                line = line.strip().lstrip("-•*").strip()
                if line:
                    changes_made.append(line)

        # --- needs revision ------------------------------------------------
        needs_revision = False
        revision_reason = ""
        if rewrite_idx != -1:
            rewrite_line = text[rewrite_idx + len(_REWRITE_MARKER):].strip().splitlines()
            first_line = rewrite_line[0].strip() if rewrite_line else ""
            if first_line.upper().startswith("YES"):
                needs_revision = True
                revision_reason = re.sub(r"^YES\s*:?\s*", "", first_line, flags=re.I).strip()

        return revised_draft, changes_made, needs_revision, revision_reason
