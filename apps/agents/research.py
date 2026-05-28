"""
Research Agent — gathers information on the topic using Tavily + BeautifulSoup.

Token optimisation:
  • Each source is truncated to 1500 characters before being passed on.
  • Final research_summary is capped at 3000 characters.
  • Uses Tavily's AI-preprocessed search results (less LLM work needed).
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from django.conf import settings

from apps.pipeline.state import PipelineState, SourceDocument

from .base import BaseAgent

logger = logging.getLogger(__name__)

MAX_SOURCES = 6
SOURCE_CONTENT_LIMIT = 1500   # chars per source (token budget)
SUMMARY_LIMIT = 3000          # chars for research_summary


class ResearchAgent(BaseAgent):
    name = "research"

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    def run(self, state: PipelineState) -> PipelineState:
        logger.info("[ResearchAgent] Starting research for: %s", state.topic[:80])
        state.current_agent = self.name

        raw_sources = self._search_tavily(state.topic, state.keywords)
        sources = self._scrape_and_trim(raw_sources)
        state.sources = sources[:MAX_SOURCES]

        state.research_summary = self._summarise(state)
        if state.sources:
            self._track_usage(state, calls=1)

        logger.info(
            "[ResearchAgent] Done — %d sources, summary %d chars",
            len(state.sources),
            len(state.research_summary),
        )
        return state

    # ------------------------------------------------------------------ #
    # Tavily search
    # ------------------------------------------------------------------ #

    def _search_tavily(self, topic: str, keywords: list[str]) -> list[dict]:
        if not getattr(settings, "ENABLE_WEB_SEARCH", True):
            logger.info("[ResearchAgent] Web search disabled by settings.")
            return []

        api_key = getattr(settings, "TAVILY_API_KEY", "")
        if not api_key:
            logger.warning("[ResearchAgent] TAVILY_API_KEY not set — skipping web search.")
            return []

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            query = topic
            if keywords:
                query = f"{topic} ({', '.join(keywords[:3])})"

            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=MAX_SOURCES,
                include_raw_content=True,
            )
            return response.get("results", [])
        except Exception as exc:
            logger.error("[ResearchAgent] Tavily search failed: %s", exc)
            return []

    # ------------------------------------------------------------------ #
    # Scrape & trim
    # ------------------------------------------------------------------ #

    def _scrape_and_trim(self, raw_results: list[dict]) -> list[SourceDocument]:
        sources: list[SourceDocument] = []

        for item in raw_results:
            url = item.get("url", "")
            title = item.get("title", urlparse(url).netloc)

            # Prefer Tavily's pre-extracted raw_content; fallback to snippet
            content = item.get("raw_content") or item.get("content", "")

            if not content:
                content = self._scrape_url(url)

            # Trim to budget
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
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            # Remove nav/footer/script noise
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)[:SOURCE_CONTENT_LIMIT]
        except Exception as exc:
            logger.debug("[ResearchAgent] Could not scrape %s: %s", url, exc)
            return ""

    # ------------------------------------------------------------------ #
    # Gemini summarisation (1 LLM call)
    # ------------------------------------------------------------------ #

    def _summarise(self, state: PipelineState) -> str:
        if not state.sources:
            return ""

        source_text = "\n\n".join(
            f"Source {i+1}: {s.title}\n{s.content}"
            for i, s in enumerate(state.sources)
        )

        system_prompt = (
            "You are a research assistant. Summarise the provided sources "
            "into a concise, factual overview. Focus on key facts, statistics, "
            "and viewpoints relevant to the topic. Maximum 300 words."
        )
        user_prompt = (
            f"Topic: {state.topic}\n\n"
            f"Sources:\n{source_text}\n\n"
            "Write a 200-300 word research summary."
        )

        response = self._call_llm(system_prompt, user_prompt)
        return self._text(response)[:SUMMARY_LIMIT]
