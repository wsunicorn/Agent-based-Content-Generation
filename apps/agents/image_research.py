"""Image Research Agent.

Automatically finds reusable images for the article from Wikimedia Commons and
stores them as visual assets. No user upload is required.
"""
from __future__ import annotations

import html
import logging
import re
from urllib.parse import quote_plus

from django.conf import settings
import httpx

from apps.pipeline.state import ImageAsset, PipelineState, SourceDocument

from .base import BaseAgent
from .domain_guides import get_domain_search_terms

logger = logging.getLogger(__name__)

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"


class ImageResearchAgent(BaseAgent):
    name = "image_research"
    temperature = 0.1
    timeout = 30

    def run(self, state: PipelineState) -> PipelineState:
        state.current_agent = self.name
        if not getattr(settings, "IMAGE_SEARCH_ENABLED", True):
            state.image_assets = []
            return state

        provider = getattr(settings, "IMAGE_SEARCH_PROVIDER", "wikimedia_commons").lower()
        if provider not in {"wikimedia_commons", "commons", "tavily"}:
            logger.warning("[ImageResearchAgent] Unsupported image provider: %s", provider)
            state.image_assets = []
            return state

        query = ""
        assets: list[ImageAsset] = []
        for candidate in self._query_candidates(state):
            query = candidate
            if provider == "tavily":
                assets = self._search_tavily(candidate, state)
            else:
                assets = self._search_commons(candidate, state)
            if assets:
                break

        # Automatically fall back to Tavily Image Search if Wikimedia returned no results and Tavily API key is available
        if not assets and provider != "tavily" and getattr(settings, "TAVILY_API_KEY", ""):
            logger.info("[ImageResearchAgent] Wikimedia Commons returned no results. Falling back to Tavily Image Search.")
            for candidate in self._query_candidates(state):
                query = candidate
                assets = self._search_tavily(candidate, state)
                if assets:
                    break

        state.image_assets = assets[: self._max_images(state)]

        if state.image_assets:
            image_sources = [
                SourceDocument(
                    url=asset.source_url or asset.url,
                    title=asset.title,
                    content=(
                        f"Image asset for article: {asset.caption or asset.alt_text}. "
                        f"Attribution: {asset.attribution}. License: {asset.license}."
                    ),
                    source_type="image",
                )
                for asset in state.image_assets
            ]
            non_image_sources = [
                source for source in state.sources if source.source_type != "image"
            ]
            state.sources = image_sources + non_image_sources

        logger.info(
            "[ImageResearchAgent] Found %d image asset(s) for query=%s",
            len(state.image_assets),
            query,
        )
        return state

    def _query_candidates(self, state: PipelineState) -> list[str]:
        topic = self._clean_query(state.topic)
        keywords = [self._clean_query(kw) for kw in state.keywords[:3] if kw]
        domain_terms = self._clean_query(get_domain_search_terms(getattr(state, "domain", "")))

        candidates = [
            " ".join([topic, *keywords[:1]]).strip(),
            topic,
            " ".join(keywords[:2]).strip(),
            self._build_query(state),
            domain_terms,
        ]

        unique_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate = self._clean_query(candidate)
            if not candidate or candidate.lower() in seen:
                continue
            seen.add(candidate.lower())
            unique_candidates.append(candidate[:160])
        return unique_candidates

    def _build_query(self, state: PipelineState) -> str:
        terms = [state.topic]
        if state.keywords:
            terms.extend(state.keywords[:2])
        raw = " ".join(term for term in terms if term)
        return self._clean_query(raw)[:160]

    @staticmethod
    def _clean_query(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _search_tavily(self, query: str, state: PipelineState) -> list[ImageAsset]:
        if not query:
            return []

        api_key = getattr(settings, "TAVILY_API_KEY", "")
        if not api_key:
            logger.warning("[ImageResearchAgent] TAVILY_API_KEY not set - skipping Tavily image search.")
            return []

        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            response = client.search(
                query=query,
                include_images=True,
                max_results=max(3, self._max_images(state) * 2),
            )
            image_urls = response.get("images", [])
            assets: list[ImageAsset] = []
            for i, url in enumerate(image_urls):
                if not url:
                    continue
                caption = self._caption_for_asset(f"Ảnh {i + 1}", state)
                alt_text = f"Ảnh minh họa liên quan đến {state.topic}"
                assets.append(
                    ImageAsset(
                        title=f"Ảnh {i + 1}",
                        url=url,
                        thumbnail_url=url,
                        source_url=url,
                        alt_text=alt_text[:180],
                        caption=caption[:240],
                        attribution="Web Search",
                        license="Creative Commons / Fair Use via Web Search",
                        provider="tavily",
                        width=800,
                        height=600,
                    )
                )
            return assets
        except Exception as exc:
            logger.warning("[ImageResearchAgent] Tavily image search failed: %s", exc)
            return []

    def _search_commons(self, query: str, state: PipelineState) -> list[ImageAsset]:
        if not query:
            return []

        limit = max(self._max_images(state) * 3, 6)
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrsearch": query,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": 1200,
            "origin": "*",
        }

        headers = {
            "User-Agent": getattr(
                settings,
                "IMAGE_SEARCH_USER_AGENT",
                "DomainLLMAssistant/1.0 (local development)",
            )
        }

        try:
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                response = client.get(COMMONS_API_URL, params=params)
                response.raise_for_status()
                pages = (response.json().get("query", {}) or {}).get("pages", {})
        except Exception as exc:
            logger.warning("[ImageResearchAgent] Wikimedia Commons search failed: %s", exc)
            return []

        assets: list[ImageAsset] = []
        seen_urls: set[str] = set()
        for page in pages.values():
            asset = self._asset_from_page(page, state)
            if not asset or asset.url in seen_urls:
                continue
            seen_urls.add(asset.url)
            assets.append(asset)
            if len(assets) >= self._max_images(state):
                break
        return assets

    def _asset_from_page(self, page: dict, state: PipelineState) -> ImageAsset | None:
        image_info = (page.get("imageinfo") or [{}])[0]
        mime = image_info.get("mime", "")
        if not str(mime).startswith("image/"):
            return None

        url = image_info.get("url", "")
        if not url:
            return None

        metadata = image_info.get("extmetadata") or {}
        title = _clean_title(page.get("title", "Image"))
        description = _metadata_value(metadata, "ImageDescription")
        object_name = _metadata_value(metadata, "ObjectName") or title
        license_name = _metadata_value(metadata, "LicenseShortName") or _metadata_value(metadata, "UsageTerms")
        attribution = (
            _metadata_value(metadata, "Artist")
            or _metadata_value(metadata, "Credit")
            or "Wikimedia Commons contributor"
        )
        source_url = image_info.get("descriptionurl", "")

        caption = self._caption_for_asset(object_name, state)
        alt_text = self._alt_text_for_asset(object_name, description, state)

        return ImageAsset(
            title=object_name[:180],
            url=url,
            thumbnail_url=image_info.get("thumburl", url),
            source_url=source_url,
            alt_text=alt_text[:180],
            caption=caption[:240],
            attribution=attribution[:240],
            license=license_name[:120],
            provider="wikimedia_commons",
            width=int(image_info.get("width") or 0),
            height=int(image_info.get("height") or 0),
        )

    @staticmethod
    def _caption_for_asset(name: str, state: PipelineState) -> str:
        topic = state.topic.strip()
        language = (getattr(state, "language", "") or "").lower()
        if "vietnam" in language or "viet" in language:
            if topic:
                return f"Anh minh hoa lien quan den {topic}: {name}."
            return f"Anh minh hoa: {name}."
        if topic:
            return f"Illustration related to {topic}: {name}."
        return f"Illustration: {name}."

    @staticmethod
    def _alt_text_for_asset(name: str, description: str, state: PipelineState) -> str:
        text = description or name
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text
        return f"Image related to {state.topic}."

    @staticmethod
    def _max_images(state: PipelineState) -> int:
        configured = max(0, getattr(settings, "IMAGE_SEARCH_MAX_RESULTS", 2))
        if state.quality_mode == "fast":
            return min(configured, 1)
        return configured


def markdown_for_image(asset: ImageAsset) -> str:
    source = asset.source_url or asset.url
    source_label = "Wikimedia Commons" if asset.provider == "wikimedia_commons" else "source"
    caption = (asset.caption or asset.title).strip()
    caption_text = caption if caption.endswith((".", "!", "?")) else f"{caption}."
    attribution = f" {asset.attribution}." if asset.attribution else ""
    license_text = f" License: {asset.license}." if asset.license else ""
    source_text = f" Source: [{source_label}]({source})." if source else ""
    return (
        f"![{asset.alt_text or asset.title}]({asset.url})\n\n"
        f"*{caption_text}{attribution}{license_text}{source_text}*"
    )


def _metadata_value(metadata: dict, key: str) -> str:
    value = metadata.get(key, {})
    if isinstance(value, dict):
        value = value.get("value", "")
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _clean_title(title: str) -> str:
    title = str(title or "Image")
    title = re.sub(r"^File:", "", title, flags=re.I)
    title = re.sub(r"\.[a-z0-9]{2,5}$", "", title, flags=re.I)
    title = title.replace("_", " ")
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def commons_search_url(query: str) -> str:
    return f"https://commons.wikimedia.org/w/index.php?search={quote_plus(query)}&title=Special:MediaSearch&type=image"
