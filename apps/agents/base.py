"""Shared base class for all agents in the pipeline."""
from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Type

from django.conf import settings
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.pipeline.state import PipelineState

from .llm_providers import (
    GeminiDailyQuotaExceeded,
    build_provider,
    normalise_provider_name,
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all pipeline agents."""

    name: str = "base"
    model: str = ""
    temperature: float = 0.7
    max_retries: int = 3
    timeout: int = 60

    def __init__(self):
        self._provider_cache = {}
        self._last_provider_name = "unknown"

    # ------------------------------------------------------------------ #
    # Provider routing
    # ------------------------------------------------------------------ #

    def _select_provider_name(self, output_schema: Type[BaseModel] | None = None) -> str:
        """Choose the provider for this call based on env mode and agent role."""
        agent_provider = getattr(settings, "LLM_AGENT_PROVIDERS", {}).get(self.name)
        if agent_provider:
            return normalise_provider_name(agent_provider)

        configured = normalise_provider_name(getattr(settings, "LLM_PROVIDER", "gemini"))
        if configured != "hybrid":
            return configured

        mode = getattr(settings, "LLM_MODE", "balanced").lower()
        local_provider = normalise_provider_name(getattr(settings, "LOCAL_LLM_PROVIDER", "ollama"))
        structured_provider = normalise_provider_name(
            getattr(settings, "STRUCTURED_LLM_PROVIDER", "gemini")
        )
        local_agents = set(getattr(settings, "LOCAL_LLM_AGENTS", []))

        if mode == "cheap":
            if output_schema is not None and settings.GOOGLE_API_KEY:
                return structured_provider
            return local_provider

        if mode == "quality":
            return "gemini" if settings.GOOGLE_API_KEY else local_provider

        # balanced: use local for prose-heavy agents and Gemini for structured
        # outputs or orchestration-sensitive steps.
        if output_schema is not None:
            if structured_provider != "gemini" or settings.GOOGLE_API_KEY:
                return structured_provider
            return local_provider
        if self.name in local_agents:
            return local_provider
        return "gemini" if settings.GOOGLE_API_KEY else local_provider

    def _get_provider(self, provider_name: str):
        provider_name = normalise_provider_name(provider_name)
        model_name = self._select_model_name(provider_name)
        cache_key = f"{provider_name}:{model_name or 'default'}"
        if cache_key not in self._provider_cache:
            timeout = self.timeout
            if provider_name != "gemini":
                timeout = max(timeout, getattr(settings, "LOCAL_LLM_TIMEOUT", timeout))
            self._provider_cache[cache_key] = build_provider(
                provider_name=provider_name,
                agent_model=model_name,
                temperature=self.temperature,
                timeout=timeout,
            )
        return self._provider_cache[cache_key]

    def _select_model_name(self, provider_name: str) -> str:
        """Return an optional per-agent model override for the selected provider."""
        provider_name = normalise_provider_name(provider_name)
        if provider_name == "gemini":
            return getattr(settings, "GEMINI_AGENT_MODELS", {}).get(self.name, self.model)
        return getattr(settings, "LLM_AGENT_MODELS", {}).get(self.name, self.model)

    @staticmethod
    def _request_delay(provider_name: str) -> float:
        if normalise_provider_name(provider_name) == "gemini":
            return settings.GEMINI_REQUEST_DELAY
        return getattr(settings, "LOCAL_LLM_REQUEST_DELAY", 0.0)

    # ------------------------------------------------------------------ #
    # LLM call with provider routing, retry, and optional fallback
    # ------------------------------------------------------------------ #

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[BaseModel] | None = None,
    ) -> Any:
        """
        Call the configured LLM with optional Pydantic structured output.
        Local providers can fall back to Gemini when enabled and available.
        """
        provider_name = self._select_provider_name(output_schema)
        time.sleep(self._request_delay(provider_name))

        @retry(
            retry=retry_if_exception_type(Exception),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=2,
                min=max(1, self._request_delay(provider_name)),
                max=120,
            ),
            reraise=True,
        )
        def _invoke():
            try:
                self._last_provider_name = provider_name
                return self._get_provider(provider_name).generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                )
            except Exception as exc:
                if (
                    provider_name != "gemini"
                    and settings.LLM_FALLBACK_TO_GEMINI
                    and settings.GOOGLE_API_KEY
                ):
                    logger.warning(
                        "[%s] %s provider failed, falling back to Gemini: %s",
                        self.name,
                        provider_name,
                        exc,
                    )
                    try:
                        time.sleep(self._request_delay("gemini"))
                        self._last_provider_name = "gemini"
                        return self._get_provider("gemini").generate(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            output_schema=output_schema,
                        )
                    except Exception as fallback_exc:
                        self._handle_llm_exception(fallback_exc)
                        raise

                self._handle_llm_exception(exc)
                raise

        return _invoke()

    def _handle_llm_exception(self, exc: Exception) -> None:
        err_str = str(exc)
        if "PerDay" in err_str and "429" in err_str:
            raise GeminiDailyQuotaExceeded(
                "Gemini free-tier daily request limit reached. "
                "Quota resets at midnight Pacific Time. "
                "Original error: " + err_str
            ) from exc
        if "429" in err_str:
            match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err_str)
            if match:
                wait_secs = int(match.group(1)) + 5
                logger.warning(
                    "[%s] 429 rate limit - waiting %ds as suggested by API",
                    self.name,
                    wait_secs,
                )
                time.sleep(wait_secs)

    # ------------------------------------------------------------------ #
    # Usage helpers
    # ------------------------------------------------------------------ #

    def _track_usage(self, state: PipelineState, calls: int = 1, tokens: int = 0) -> None:
        state.llm_calls_total += calls
        state.llm_tokens_total += tokens

        provider_name = getattr(self, "_last_provider_name", "unknown")
        state.llm_calls_by_provider[provider_name] = (
            state.llm_calls_by_provider.get(provider_name, 0) + calls
        )
        state.llm_tokens_by_provider[provider_name] = (
            state.llm_tokens_by_provider.get(provider_name, 0) + tokens
        )

        daily_limit = getattr(settings, "GEMINI_DAILY_LIMIT", 250)
        warn_at = getattr(settings, "GEMINI_DAILY_WARN_AT", 200)
        gemini_calls = state.llm_calls_by_provider.get("gemini", 0)

        if gemini_calls >= daily_limit:
            logger.error(
                "GEMINI DAILY LIMIT REACHED: %d/%d calls used.",
                gemini_calls,
                daily_limit,
            )
        elif gemini_calls >= warn_at:
            logger.warning(
                "Gemini usage warning: %d/%d daily calls used.",
                gemini_calls,
                daily_limit,
            )

    # ------------------------------------------------------------------ #
    # Abstract interface
    # ------------------------------------------------------------------ #

    @abstractmethod
    def run(self, state: PipelineState) -> PipelineState:
        """Execute the agent and return the updated state."""
        ...

    # ------------------------------------------------------------------ #
    # Utility: extract plain text from LLM response
    # ------------------------------------------------------------------ #

    @staticmethod
    def _text(response) -> str:
        if hasattr(response, "content"):
            return response.content.strip()
        return str(response).strip()
