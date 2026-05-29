"""Research agent with cached web search, scrape, and summary output."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache

from apps.pipeline.state import PipelineState, SourceDocument

from .base import BaseAgent
from .domain_guides import get_domain_guide_text, get_domain_search_terms

logger = logging.getLogger(__name__)

SOURCE_CONTENT_LIMIT = 1500
SUMMARY_LIMIT = 3000


class ResearchAgent(BaseAgent):
    name = "research"

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[ResearchAgent] Starting research for: %s", state.topic[:80])
        state.current_agent = self.name

        image_sources = [
            source
            for source in state.sources
            if source.source_type == "image"
        ]
        raw_sources = self._search_tavily(state)
        sources = self._scrape_and_trim(raw_sources)
        state.sources = image_sources + sources[: self._max_sources(state)]

        state.research_summary = self._summarise(state)
        if state.sources and not self._summary_was_cached:
            self._track_usage(state, calls=1)

        logger.info(
            "[ResearchAgent] Done - %d sources, summary %d chars",
            len(state.sources),
            len(state.research_summary),
        )
        return state

    def __init__(self):
        super().__init__()
        self._summary_was_cached = False

    def _search_tavily(self, state: PipelineState) -> list[dict]:
        if state.quality_mode == "fast" and not getattr(settings, "FAST_MODE_WEB_SEARCH", False):
            logger.info("[ResearchAgent] Fast mode web search disabled.")
            return []

        if not getattr(settings, "ENABLE_WEB_SEARCH", True):
            logger.info("[ResearchAgent] Web search disabled by settings.")
            return []

        api_key = getattr(settings, "TAVILY_API_KEY", "")
        if not api_key:
            logger.warning("[ResearchAgent] TAVILY_API_KEY not set - skipping web search.")
            return []

        query = self._build_search_query(state)
        cache_key = self._cache_key("search:v2", query, state.language, state.domain)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("[ResearchAgent] Tavily cache hit.")
            return cached

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)

            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=max(1, getattr(settings, "RESEARCH_MAX_SOURCES", 4)),
                include_raw_content=True,
            )
            results = response.get("results", [])
            cache.set(
                cache_key,
                results,
                timeout=max(60, getattr(settings, "RESEARCH_CACHE_TTL", 86400)),
            )
            return results
        except Exception as exc:
            logger.error("[ResearchAgent] Tavily search failed: %s", exc)
            return []

    @staticmethod
    def _build_search_query(state: PipelineState) -> str:
        """Build a deterministic query that keeps the user topic dominant."""
        topic = " ".join(str(state.topic or "").split()).strip()
        keyword_text = " ".join(
            keyword
            for keyword in (str(item).strip() for item in state.keywords[:3])
            if keyword and keyword.lower() not in topic.lower()
        )
        query = f"{topic} {keyword_text}".strip() or keyword_text

        domain = str(state.domain or "").lower()
        if domain not in {"general", "food"} and len(re.findall(r"\w+", query)) <= 4:
            query = f"{query} {get_domain_search_terms(domain)}".strip()

        return query[:160] or "general information"

    def _scrape_and_trim(self, raw_results: list[dict]) -> list[SourceDocument]:
        sources: list[SourceDocument] = []

        for item in raw_results:
            url = item.get("url", "")
            title = item.get("title", urlparse(url).netloc)
            content = item.get("raw_content") or item.get("content", "")

            if not content and url:
                content = self._scrape_url(url)

            content = content[:SOURCE_CONTENT_LIMIT]
            if content:
                sources.append(
                    SourceDocument(
                        url=url,
                        title=title,
                        content=content,
                        source_type="web",
                    )
                )

        return sources

    def _scrape_url(self, url: str) -> str:
        cache_key = self._cache_key("scrape", url)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("[ResearchAgent] Scrape cache hit for %s", urlparse(url).netloc)
            return cached

        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            content = soup.get_text(separator=" ", strip=True)[:SOURCE_CONTENT_LIMIT]
            cache.set(
                cache_key,
                content,
                timeout=max(60, getattr(settings, "SCRAPE_CACHE_TTL", 604800)),
            )
            return content
        except Exception as exc:
            logger.debug("[ResearchAgent] Could not scrape %s: %s", url, exc)
            return ""

    def _summarise(self, state: PipelineState) -> str:
        self._summary_was_cached = False
        text_sources = [
            source for source in state.sources if source.source_type != "image"
        ]
        if not text_sources:
            return ""

        cache_key = self._cache_key(
            "summary",
            state.topic,
            state.domain,
            state.audience,
            state.keywords,
            [source.url for source in text_sources],
            [source.content[:300] for source in text_sources],
        )
        cached = cache.get(cache_key)
        if cached is not None:
            self._summary_was_cached = True
            logger.info("[ResearchAgent] Summary cache hit.")
            return cached

        source_text = "\n\n".join(
            f"Source {i + 1}: {source.title}\n{source.content}"
            for i, source in enumerate(text_sources)
        )

        system_prompt = (
            "You are a research assistant. Summarise the provided sources into a "
            "concise, factual overview. Focus on key facts, statistics, and "
            "viewpoints relevant to the user's exact topic. Maximum 300 words. "
            "Do not let broad domain context replace the topic; if a source is only "
            "adjacent, describe that limitation briefly."
        )
        user_prompt = (
            f"Topic: {state.topic}\n\n"
            f"Domain guide:\n{get_domain_guide_text(state.domain, state.audience, state.tone)}\n\n"
            f"Sources:\n{source_text}\n\n"
            "Write a 200-300 word research summary. Prioritise direct topic evidence, "
            "then add domain caveats, terminology, and safety/compliance cautions only when useful."
        )

        response = self._call_llm(system_prompt, user_prompt)
        summary = self._text(response)[:SUMMARY_LIMIT]
        cache.set(
            cache_key,
            summary,
            timeout=max(60, getattr(settings, "RESEARCH_CACHE_TTL", 86400)),
        )
        return summary

    @staticmethod
    def _cache_key(prefix: str, *parts) -> str:
        raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"research:{prefix}:{digest}"

    @staticmethod
    def _max_sources(state: PipelineState) -> int:
        configured = max(1, getattr(settings, "RESEARCH_MAX_SOURCES", 4))
        if state.quality_mode == "fast":
            return min(configured, 2)
        if state.quality_mode == "strict":
            return max(configured, 6)
        return configured
