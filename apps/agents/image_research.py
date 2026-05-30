"""Image Research Agent.

Automatically finds reusable images for the article and stores them as visual
assets. Wikimedia Commons is preferred; Tavily can be used as a fallback.
"""
from __future__ import annotations

import html
import logging
import re
from urllib.parse import quote_plus, urlparse

from django.conf import settings
import httpx

from apps.pipeline.state import ImageAsset, PipelineState, SourceDocument

from .base import BaseAgent
from .domain_guides import get_domain_search_terms

logger = logging.getLogger(__name__)

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")
REJECTED_IMAGE_EXTENSIONS = (".pdf", ".html", ".htm", ".php", ".aspx")
UNRELIABLE_IMAGE_HOST_PARTS = (
    "facebook.com",
    "fbcdn.net",
    "fbsbx.com",
    "instagram.com",
    "cdninstagram.com",
    "pinterest.",
    "pinimg.com",
    "tiktokcdn.com",
)


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

        assets = self._search_targets(provider, state)

        if (
            len(assets) < self._max_images(state)
            and provider != "tavily"
            and getattr(settings, "TAVILY_API_KEY", "")
        ):
            logger.info(
                "[ImageResearchAgent] Wikimedia Commons returned %d/%d image(s). "
                "Filling remaining slots with Tavily Image Search.",
                len(assets),
                self._max_images(state),
            )
            seen_urls = {asset.url for asset in assets}
            assets.extend(self._search_targets("tavily", state, seen_urls=seen_urls))

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
            "[ImageResearchAgent] Found %d image asset(s) for %d target(s)",
            len(state.image_assets),
            len(self._image_targets(state)),
        )
        return state

    def _search_targets(
        self,
        provider: str,
        state: PipelineState,
        seen_urls: set[str] | None = None,
    ) -> list[ImageAsset]:
        """Search one targeted visual per intro/body section before broad fill."""
        max_images = self._max_images(state)
        if max_images <= 0:
            return []

        assets: list[ImageAsset] = []
        seen = set(seen_urls or set())
        targets = self._image_targets(state)

        for target in targets:
            if len(assets) >= max_images:
                break
            found = self._search_first_match(provider, state, target, seen)
            if found:
                assets.append(found)
                seen.add(found.url)

        if len(assets) >= max_images:
            return assets

        for candidate in self._query_candidates(state):
            if len(assets) >= max_images:
                break
            remaining = max_images - len(assets)
            extra = self._search_provider(
                provider,
                candidate,
                state,
                limit=remaining,
                target_label=state.topic,
            )
            for asset in extra:
                if asset.url in seen:
                    continue
                assets.append(asset)
                seen.add(asset.url)
                if len(assets) >= max_images:
                    break

        return assets

    def _search_first_match(
        self,
        provider: str,
        state: PipelineState,
        target: dict[str, str],
        seen_urls: set[str],
    ) -> ImageAsset | None:
        for candidate in self._target_query_candidates(state, target):
            found = self._search_provider(
                provider,
                candidate,
                state,
                limit=1,
                target_label=target["label"],
            )
            for asset in found:
                if asset.url not in seen_urls:
                    return asset
        return None

    def _search_provider(
        self,
        provider: str,
        query: str,
        state: PipelineState,
        *,
        limit: int,
        target_label: str = "",
    ) -> list[ImageAsset]:
        if provider == "tavily":
            return self._search_tavily(query, state, limit=limit, target_label=target_label)
        return self._search_commons(query, state, limit=limit, target_label=target_label)

    def _image_targets(self, state: PipelineState) -> list[dict[str, str]]:
        topic = self._clean_query(state.topic)
        targets: list[dict[str, str]] = []
        if topic:
            targets.append({"label": topic, "query": self._build_query(state)})

        for section in state.sections:
            heading = self._clean_query(section.heading)
            if not heading:
                continue
            key_points = self._clean_query(" ".join(section.key_points[:2]))
            query = self._clean_query(" ".join(part for part in (topic, heading, key_points) if part))
            targets.append({"label": heading, "query": query[:180]})

        unique: list[dict[str, str]] = []
        seen_labels: set[str] = set()
        for target in targets:
            label_key = target["label"].lower()
            if label_key in seen_labels:
                continue
            seen_labels.add(label_key)
            unique.append(target)
        return unique[: self._max_images(state)]

    def _target_query_candidates(self, state: PipelineState, target: dict[str, str]) -> list[str]:
        candidates = [
            target.get("query", ""),
            " ".join([state.topic, target.get("label", "")]).strip(),
            *self._query_candidates(state),
        ]
        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate = self._clean_query(candidate)
            if not candidate or candidate.lower() in seen:
                continue
            seen.add(candidate.lower())
            unique.append(candidate[:180])
        return unique

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

    def _search_tavily(
        self,
        query: str,
        state: PipelineState,
        *,
        limit: int | None = None,
        target_label: str = "",
    ) -> list[ImageAsset]:
        if not query:
            return []

        api_key = getattr(settings, "TAVILY_API_KEY", "")
        if not api_key:
            logger.warning("[ImageResearchAgent] TAVILY_API_KEY not set - skipping Tavily image search.")
            return []

        try:
            from tavily import TavilyClient

            max_images = max(0, limit if limit is not None else self._max_images(state))
            client = TavilyClient(api_key=api_key)
            response = client.search(
                query=query,
                include_images=True,
                max_results=max(3, max_images * 3),
            )
            image_items = response.get("images", [])
            assets: list[ImageAsset] = []

            for raw_item in image_items:
                url = self._extract_image_url(raw_item)
                if not url or not self._is_reliable_image_url(url):
                    continue
                if not self._validate_image_url(url):
                    logger.debug("[ImageResearchAgent] Skipping non-displayable image URL: %s", url)
                    continue

                index = len(assets) + 1
                title = self._image_title(raw_item, index, fallback=target_label)
                source_url = self._image_source_url(raw_item) or url
                caption = self._caption_for_asset(title, state, target_label=target_label)
                assets.append(
                    ImageAsset(
                        title=title,
                        url=url,
                        thumbnail_url=url,
                        source_url=source_url,
                        alt_text=self._alt_text_for_asset(title, "", state, target_label=target_label)[:180],
                        caption=caption[:240],
                        attribution="Web Search",
                        license="Reusable web image; verify rights before publication",
                        provider="tavily",
                        width=800,
                        height=600,
                    )
                )
                if len(assets) >= max_images:
                    break
            return assets
        except Exception as exc:
            logger.warning("[ImageResearchAgent] Tavily image search failed: %s", exc)
            return []

    @staticmethod
    def _extract_image_url(raw_item) -> str:
        if isinstance(raw_item, str):
            return raw_item.strip()
        if isinstance(raw_item, dict):
            for key in ("url", "image_url", "src", "thumbnail_url"):
                value = str(raw_item.get(key) or "").strip()
                if value:
                    return value
        return ""

    @staticmethod
    def _image_title(raw_item, index: int, fallback: str = "") -> str:
        if isinstance(raw_item, dict):
            for key in ("title", "alt", "description"):
                value = str(raw_item.get(key) or "").strip()
                if value:
                    return value[:180]
        if fallback:
            return fallback[:180]
        return f"Image {index}"

    @staticmethod
    def _image_source_url(raw_item) -> str:
        if not isinstance(raw_item, dict):
            return ""
        for key in ("source_url", "page_url", "origin_url"):
            value = str(raw_item.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _is_reliable_image_url(url: str) -> bool:
        url = str(url or "").strip()
        if not url or any(char.isspace() for char in url):
            return False

        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"}:
            return False

        host = (parsed.hostname or "").lower()
        if not host:
            return False
        if any(part in host for part in UNRELIABLE_IMAGE_HOST_PARTS):
            return False

        path = parsed.path.lower()
        filename = path.rsplit("/", 1)[-1]
        if path.endswith(REJECTED_IMAGE_EXTENSIONS):
            return False
        if "." in filename and not path.endswith(ALLOWED_IMAGE_EXTENSIONS):
            return False
        return True

    def _validate_image_url(self, url: str) -> bool:
        """Verify that an image URL can be fetched directly by a browser."""
        headers = {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "User-Agent": getattr(
                settings,
                "IMAGE_SEARCH_USER_AGENT",
                "DomainLLMAssistant/1.0 (local development)",
            ),
        }
        try:
            with httpx.Client(timeout=6, follow_redirects=True, headers=headers) as client:
                response = client.head(url)
                if response.status_code in {403, 405} or not self._response_is_image(response):
                    response = client.get(url, headers={**headers, "Range": "bytes=0-2048"})
                if not self._is_reliable_image_url(str(response.url)):
                    return False
                return self._response_is_image(response)
        except Exception:
            return False

    @staticmethod
    def _response_is_image(response: httpx.Response) -> bool:
        if response.status_code >= 400:
            return False
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type.startswith("image/"):
            return True
        path = urlparse(str(response.url)).path.lower()
        return not content_type and path.endswith(ALLOWED_IMAGE_EXTENSIONS)

    def _search_commons(
        self,
        query: str,
        state: PipelineState,
        *,
        limit: int | None = None,
        target_label: str = "",
    ) -> list[ImageAsset]:
        if not query:
            return []

        max_images = max(0, limit if limit is not None else self._max_images(state))
        search_limit = max(max_images * 3, 6)
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrsearch": query,
            "gsrlimit": search_limit,
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
            asset = self._asset_from_page(page, state, target_label=target_label)
            if not asset or asset.url in seen_urls:
                continue
            seen_urls.add(asset.url)
            assets.append(asset)
            if len(assets) >= max_images:
                break
        return assets

    def _asset_from_page(
        self,
        page: dict,
        state: PipelineState,
        *,
        target_label: str = "",
    ) -> ImageAsset | None:
        image_info = (page.get("imageinfo") or [{}])[0]
        mime = image_info.get("mime", "")
        if not str(mime).startswith("image/"):
            return None

        url = image_info.get("url", "")
        if not url or not self._is_reliable_image_url(url):
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

        caption = self._caption_for_asset(object_name, state, target_label=target_label)
        alt_text = self._alt_text_for_asset(object_name, description, state, target_label=target_label)

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
    def _caption_for_asset(name: str, state: PipelineState, target_label: str = "") -> str:
        topic = (target_label or state.topic).strip()
        language = (getattr(state, "language", "") or "").lower()
        if "vietnam" in language or "viet" in language:
            if topic:
                return f"Ảnh minh họa cho {topic}: {name}."
            return f"Ảnh minh họa: {name}."
        if topic:
            return f"Illustration related to {topic}: {name}."
        return f"Illustration: {name}."

    @staticmethod
    def _alt_text_for_asset(
        name: str,
        description: str,
        state: PipelineState,
        target_label: str = "",
    ) -> str:
        text = description or name
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text
        target = target_label or state.topic
        return f"Image related to {target}."

    @staticmethod
    def _max_images(state: PipelineState) -> int:
        configured = max(0, getattr(settings, "IMAGE_SEARCH_MAX_RESULTS", 2))
        if configured == 0:
            return 0
        if state.quality_mode == "fast":
            return min(configured, 1)

        section_count = len(getattr(state, "sections", []) or [])
        if section_count:
            desired = section_count + 1
        else:
            desired = {
                "news_article": 2,
                "blog_post": 3,
                "tutorial": 4,
                "technical_report": 4,
            }.get(getattr(state, "content_type", ""), 3)

        if getattr(state, "target_length", 0) >= 2200:
            desired += 1
        if getattr(state, "quality_mode", "") == "strict":
            desired += 1
        return min(max(configured, desired), 10)


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
