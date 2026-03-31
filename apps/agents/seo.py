"""
SEO Agent — generates metadata and scores the content.

Token optimisation:
  • Pure-Python readability + keyword scoring (no LLM calls for these).
  • Only 1 LLM call to generate meta_title, meta_description, focus_keyword, slug.
"""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field, field_validator

from apps.pipeline.state import PipelineState, SEOMetadata

from .base import BaseAgent

logger = logging.getLogger(__name__)


class SEOOutput(BaseModel):
    meta_title: str
    meta_description: str
    slug: str
    focus_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)

    @field_validator("meta_title", mode="before")
    @classmethod
    def truncate_title(cls, v: str) -> str:
        return str(v)[:65]

    @field_validator("meta_description", mode="before")
    @classmethod
    def truncate_description(cls, v: str) -> str:
        return str(v)[:165]


class SEOAgent(BaseAgent):
    name = "seo"
    temperature = 0.4

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[SEOAgent] Generating SEO metadata")
        state.current_agent = self.name

        final_text = state.edited_draft or state.draft

        # Pure-Python scoring (no LLM cost)
        readability = self._readability_score(final_text)
        kw_score = self._keyword_density_score(final_text, state.keywords)

        # 1 LLM call for metadata
        metadata = self._generate_metadata(state, final_text)
        self._track_usage(state, calls=1)

        state.seo_metadata = SEOMetadata(
            meta_title=metadata.meta_title,
            meta_description=metadata.meta_description,
            slug=metadata.slug,
            focus_keyword=metadata.focus_keyword,
            secondary_keywords=metadata.secondary_keywords,
            readability_score=readability,
            seo_score=kw_score,
        )

        logger.info(
            "[SEOAgent] Done — readability=%.1f, seo=%.1f",
            readability,
            kw_score,
        )
        return state

    # ------------------------------------------------------------------ #
    # Pure-Python scoring helpers (zero LLM tokens)
    # ------------------------------------------------------------------ #

    def _readability_score(self, text: str) -> float:
        """Simplified Flesch Reading Ease score (0-100, higher = easier)."""
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        words = re.findall(r"\b\w+\b", text)

        if not sentences or not words:
            return 0.0

        avg_sentence_length = len(words) / len(sentences)

        # Approximate syllable count (vowel groups)
        def syllables(word: str) -> int:
            return max(1, len(re.findall(r"[aeiouAEIOU]+", word)))

        avg_syllables_per_word = sum(syllables(w) for w in words) / len(words)

        score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
        return round(max(0.0, min(100.0, score)), 1)

    def _keyword_density_score(self, text: str, keywords: list[str]) -> float:
        """Score 0-100 based on keyword presence and density."""
        if not keywords:
            return 50.0

        text_lower = text.lower()
        words = re.findall(r"\b\w+\b", text_lower)
        total_words = len(words) or 1

        scores = []
        for kw in keywords[:5]:
            kw_lower = kw.lower()
            count = text_lower.count(kw_lower)
            density = count / total_words * 100
            # Ideal density: 0.5% – 2.5%
            if 0.5 <= density <= 2.5:
                scores.append(100.0)
            elif density > 2.5:
                scores.append(max(0, 100 - (density - 2.5) * 30))
            elif count > 0:
                scores.append(density / 0.5 * 60)
            else:
                scores.append(0.0)

        return round(sum(scores) / len(scores), 1)

    # ------------------------------------------------------------------ #
    # Gemini metadata generation (1 LLM call)
    # ------------------------------------------------------------------ #

    def _generate_metadata(self, state: PipelineState, text: str) -> SEOOutput:
        system_prompt = (
            "You are an SEO specialist. Generate optimised metadata for an article.\n"
            "STRICT RULES — exceed these and output will be rejected:\n"
            "  meta_title: MAXIMUM 60 characters (count carefully before responding)\n"
            "  meta_description: MAXIMUM 155 characters (count carefully before responding)\n"
            "  slug: lowercase-hyphenated, no spaces\n"
            "  focus_keyword: single best keyword phrase"
        )

        # Only pass first 500 chars of article to LLM (token budget)
        snippet = text[:500]
        user_prompt = (
            f"Article topic: {state.topic}\n"
            f"Keywords: {', '.join(state.keywords) if state.keywords else 'none'}\n"
            f"Article snippet:\n{snippet}\n\n"
            "Generate SEO metadata. Remember: meta_title ≤60 chars, meta_description ≤155 chars."
        )

        result = self._call_llm(system_prompt, user_prompt, output_schema=SEOOutput)

        if isinstance(result, SEOOutput):
            return result

        # Fallback defaults
        from python_slugify import slugify
        return SEOOutput(
            meta_title=state.topic[:65],
            meta_description=f"Read about {state.topic}."[:165],
            slug=slugify(state.topic),
            focus_keyword=state.keywords[0] if state.keywords else state.topic[:30],
        )
