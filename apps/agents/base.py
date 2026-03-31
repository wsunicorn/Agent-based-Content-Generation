"""
BaseAgent — shared foundation for all agents in the pipeline.

Key features:
  • Gemini 2.5 Flash via langchain-google-genai
  • 6.5 s delay between LLM calls (free tier: 10 RPM)
  • Exponential-backoff retry with tenacity (handles 429 / 5xx)
  • Usage tracking (RPD counter stored in PipelineState)
  • Structured output via Pydantic models or plain text
"""
from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.pipeline.state import PipelineState


class GeminiDailyQuotaExceeded(Exception):
    """Raised when the free-tier daily request limit is exhausted."""

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all pipeline agents."""

    name: str = "base"
    model: str = ""             # falls back to settings.GEMINI_MODEL
    temperature: float = 0.7
    max_retries: int = 3
    timeout: int = 60

    def __init__(self):
        self._model_name = self.model or settings.GEMINI_MODEL
        self._request_delay: float = settings.GEMINI_REQUEST_DELAY
        self._llm: Optional[ChatGoogleGenerativeAI] = None

    # ------------------------------------------------------------------ #
    # LLM instance (lazy)
    # ------------------------------------------------------------------ #

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        if self._llm is None:
            self._llm = ChatGoogleGenerativeAI(
                model=self._model_name,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=self.temperature,
                request_timeout=self.timeout,
                max_output_tokens=8192,
            )
        return self._llm

    # ------------------------------------------------------------------ #
    # LLM call with rate-limit delay + retry
    # ------------------------------------------------------------------ #

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Optional[Type[BaseModel]] = None,
    ) -> Any:
        """
        Call Gemini with an optional Pydantic output schema for structured output.
        Enforces inter-call delay to respect free-tier 10 RPM limit.
        Handles 429 rate-limit errors: parses the suggested retry_delay and waits,
        or raises GeminiDailyQuotaExceeded when the daily limit is exhausted.
        """
        time.sleep(self._request_delay)

        @retry(
            retry=retry_if_exception_type(Exception),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=2, min=self._request_delay, max=120),
            reraise=True,
        )
        def _invoke():
            try:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
                if output_schema is not None:
                    structured_llm = self.llm.with_structured_output(output_schema)
                    return structured_llm.invoke(messages)
                return self.llm.invoke(messages)
            except Exception as exc:
                err_str = str(exc)
                # Check for daily quota exhaustion (PerDay quota ID)
                if "PerDay" in err_str and "429" in err_str:
                    raise GeminiDailyQuotaExceeded(
                        "Gemini free-tier daily request limit (20 req/day) reached. "
                        "Quota resets at midnight Pacific Time. "
                        "Original error: " + err_str
                    ) from exc
                # Parse suggested retry_delay from the error message and honour it
                if "429" in err_str:
                    match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err_str)
                    if match:
                        wait_secs = int(match.group(1)) + 5  # small buffer
                        logger.warning(
                            "[%s] 429 rate limit — waiting %ds as suggested by API",
                            self.name, wait_secs,
                        )
                        time.sleep(wait_secs)
                raise  # let tenacity retry with exponential backoff

        response = _invoke()
        return response

    # ------------------------------------------------------------------ #
    # Usage helpers
    # ------------------------------------------------------------------ #

    def _track_usage(self, state: PipelineState, calls: int = 1, tokens: int = 0) -> None:
        state.llm_calls_total += calls
        state.llm_tokens_total += tokens

        daily_limit = getattr(settings, "GEMINI_DAILY_LIMIT", 250)
        warn_at = getattr(settings, "GEMINI_DAILY_WARN_AT", 200)

        if state.llm_calls_total >= daily_limit:
            logger.error(
                "GEMINI DAILY LIMIT REACHED: %d/%d calls used.",
                state.llm_calls_total,
                daily_limit,
            )
        elif state.llm_calls_total >= warn_at:
            logger.warning(
                "Gemini usage warning: %d/%d daily calls used.",
                state.llm_calls_total,
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
