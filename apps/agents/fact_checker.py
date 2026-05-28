"""Fact checker with adaptive strictness by content type and quality mode."""
from __future__ import annotations

import logging
import re

from django.conf import settings
from pydantic import BaseModel, Field

from apps.pipeline.quality import is_strict_fact_check, normalise_quality_mode
from apps.pipeline.state import PipelineState

from .base import BaseAgent

logger = logging.getLogger(__name__)

DEFAULT_MAX_CLAIMS = 6
HARD_FACT_RE = re.compile(
    r"(\b\d{4}\b|\d+[%$€£]?|according to|study|report|survey|research|"
    r"statistics|data|published|announced|founded|launched|"
    r"nghiên cứu|báo cáo|khảo sát|thống kê|dữ liệu|công bố|ra mắt)",
    re.I,
)


class ClaimList(BaseModel):
    claims: list[str] = Field(
        default_factory=list,
        description="Specific, verifiable hard factual claims from the article",
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

        if not self._should_deep_check(state, text):
            state.unverified_claims = []
            state.fact_check_passed = True
            state.fact_check_report = {
                "mode": "light",
                "skipped_deep_check": True,
                "claims_checked": 0,
                "verified_claims": [],
                "unverified_claims": [],
                "source_count": len(state.sources),
            }
            logger.info("[FactCheckerAgent] Light check passed - no hard factual claims.")
            return state

        claims = self._extract_claims(state, text)
        if claims:
            self._track_usage(state, calls=1)

        source_corpus = " ".join(source.content.lower() for source in state.sources)
        if not source_corpus:
            source_corpus = state.research_summary.lower()

        verified = []
        unverified = []
        for claim in claims[: self._max_claims(state)]:
            supporting_source = self._supporting_source(claim, state)
            if supporting_source:
                verified.append(
                    {
                        "claim": claim,
                        "status": "verified",
                        "supporting_source": supporting_source,
                    }
                )
            else:
                unverified.append(
                    {
                        "claim": claim,
                        "status": "unverified",
                        "severity": "error" if is_strict_fact_check(state) else "warning",
                        "requires_revision": is_strict_fact_check(state),
                    }
                )

        state.unverified_claims = unverified
        state.fact_check_passed = not any(
            item.get("requires_revision", True) for item in unverified
        )
        state.fact_check_report = {
            "mode": "strict" if is_strict_fact_check(state) else "adaptive",
            "skipped_deep_check": False,
            "claims_checked": len(claims),
            "verified_claims": verified,
            "unverified_claims": unverified,
            "source_count": len(state.sources),
        }

        logger.info(
            "[FactCheckerAgent] %d claims checked, %d unverified",
            len(claims),
            len(unverified),
        )
        return state

    def _should_deep_check(self, state: PipelineState, text: str) -> bool:
        mode = normalise_quality_mode(state.quality_mode)
        configured = getattr(settings, "FACT_CHECK_MODE", "adaptive").lower()

        if configured == "off":
            return False
        if configured == "strict" or mode == "strict":
            return True
        if configured == "light" or mode == "fast":
            return False
        if is_strict_fact_check(state):
            return True

        if getattr(settings, "FACT_CHECK_SKIP_SOFT_CONTENT", True):
            return bool(HARD_FACT_RE.search(text[:2500]))
        return True

    def _extract_claims(self, state: PipelineState, text: str) -> list[str]:
        max_claims = self._max_claims(state)
        system_prompt = (
            "You are a fact-checking assistant. Extract only hard, externally "
            "verifiable factual claims from the article: statistics, named facts, "
            "dates, studies, reports, attributions, product/company claims. "
            "Ignore advice, opinions, generic tips, style suggestions, and common "
            "sense statements. "
            f"Return at most {max_claims} claims."
        )

        snippet = text[:1800]
        user_prompt = (
            f"Content type: {state.content_type}\n"
            f"Quality mode: {state.quality_mode}\n\n"
            f"Article text:\n{snippet}\n\n"
            f"Extract up to {max_claims} hard factual claims."
        )

        result = self._call_llm(system_prompt, user_prompt, output_schema=ClaimList)

        if isinstance(result, ClaimList):
            return [claim.strip() for claim in result.claims if claim.strip()]
        return []

    @staticmethod
    def _claim_supported(claim: str, corpus: str) -> bool:
        if not corpus.strip():
            return False

        words = FactCheckerAgent._claim_words(claim)
        if not words:
            return True
        matches = sum(1 for word in words if word in corpus)
        return (matches / len(words)) >= 0.45

    def _supporting_source(self, claim: str, state: PipelineState) -> dict:
        words = self._claim_words(claim)
        if not words:
            return {}

        best_source = None
        best_ratio = 0.0
        for source in state.sources:
            content = source.content.lower()
            ratio = sum(1 for word in words if word in content) / len(words)
            if ratio > best_ratio:
                best_ratio = ratio
                best_source = source

        if best_source and best_ratio >= 0.45:
            return {
                "title": best_source.title,
                "url": best_source.url,
                "match_ratio": round(best_ratio, 2),
            }
        return {}

    @staticmethod
    def _claim_words(claim: str) -> list[str]:
        words = re.findall(r"\w+", claim.lower(), flags=re.UNICODE)
        return [
            word
            for word in words
            if len(word) >= 4
            and word
            not in {
                "this",
                "that",
                "with",
                "from",
                "have",
                "will",
                "bài",
                "viết",
                "những",
                "được",
                "trong",
                "giúp",
            }
        ]

    @staticmethod
    def _max_claims(state: PipelineState) -> int:
        configured = max(1, getattr(settings, "FACT_CHECK_MAX_CLAIMS", DEFAULT_MAX_CLAIMS))
        mode = normalise_quality_mode(state.quality_mode)
        if mode == "fast":
            return min(configured, 3)
        if mode == "strict":
            return max(configured, 10)
        return configured
