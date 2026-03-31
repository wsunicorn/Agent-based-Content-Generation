"""
Fact Checker Agent — extracts factual claims and verifies them against sources.

Token optimisation:
  • Claim extraction: 1 LLM call (returns structured JSON list).
  • Verification: pure-Python string matching against collected source texts.
  • No second LLM call for verification (saves 1 RPM slot).
"""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from apps.pipeline.state import PipelineState

from .base import BaseAgent

logger = logging.getLogger(__name__)

MAX_CLAIMS = 10     # Limit extracted claims to keep token use low


class ClaimList(BaseModel):
    claims: list[str] = Field(
        description="List of specific, verifiable factual claims from the article"
    )


class FactCheckerAgent(BaseAgent):
    name = "fact_checker"
    temperature = 0.2

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[FactCheckerAgent] Checking facts")
        state.current_agent = self.name

        text = state.edited_draft or state.draft
        if not text:
            state.fact_check_passed = True
            return state

        # --- Extract claims (1 LLM call) ---
        claims = self._extract_claims(text)
        self._track_usage(state, calls=1)

        # --- Verify against source texts (pure Python) ---
        source_corpus = " ".join(s.content.lower() for s in state.sources)
        if not source_corpus:
            source_corpus = state.research_summary.lower()

        unverified = []
        for claim in claims[:MAX_CLAIMS]:
            if not self._claim_supported(claim, source_corpus):
                unverified.append({"claim": claim, "status": "unverified"})

        state.unverified_claims = unverified
        state.fact_check_passed = len(unverified) == 0

        logger.info(
            "[FactCheckerAgent] %d claims checked, %d unverified",
            len(claims),
            len(unverified),
        )
        return state

    # ------------------------------------------------------------------ #
    # LLM claim extraction
    # ------------------------------------------------------------------ #

    def _extract_claims(self, text: str) -> list[str]:
        system_prompt = (
            "You are a fact-checking assistant. Extract specific, verifiable factual "
            "claims from the article (statistics, named facts, dates, attributions). "
            "Return only claims that can be checked against external sources. "
            f"Return at most {MAX_CLAIMS} claims."
        )

        # Only first 2000 chars to save tokens
        snippet = text[:2000]
        user_prompt = (
            f"Article text:\n{snippet}\n\n"
            f"Extract up to {MAX_CLAIMS} verifiable claims."
        )

        result = self._call_llm(system_prompt, user_prompt, output_schema=ClaimList)

        if isinstance(result, ClaimList):
            return result.claims
        return []

    # ------------------------------------------------------------------ #
    # Pure-Python claim support check
    # ------------------------------------------------------------------ #

    @staticmethod
    def _claim_supported(claim: str, corpus: str) -> bool:
        """
        Lightweight check: does the corpus contain key terms from the claim?
        Passes if ≥ 50 % of meaningful claim words appear in the corpus.
        """
        words = re.findall(r"\b[a-z]{4,}\b", claim.lower())
        if not words:
            return True     # Too short to verify — give benefit of the doubt
        matches = sum(1 for w in words if w in corpus)
        return (matches / len(words)) >= 0.5
