"""LLM provider adapters used by all agents.

The agents call a small provider interface instead of importing a concrete
LLM SDK directly. This keeps Gemini as the stable default while allowing local
models through Ollama or any OpenAI-compatible local server such as LM Studio.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional, Type

import httpx
from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class GeminiDailyQuotaExceeded(Exception):
    """Raised when the Gemini free-tier daily request limit is exhausted."""


@dataclass
class LLMTextResponse:
    """Minimal response object compatible with BaseAgent._text()."""

    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider:
    """Base class for provider adapters."""

    name = "base"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Optional[Type[BaseModel]] = None,
    ) -> Any:
        raise NotImplementedError

    @staticmethod
    def _schema_instruction(output_schema: Type[BaseModel]) -> str:
        schema = output_schema.model_json_schema()
        return (
            "\n\nReturn only valid JSON matching this schema. Do not wrap it in "
            "Markdown fences and do not include explanatory text.\n"
            f"JSON schema:\n{json.dumps(schema, ensure_ascii=False)}"
        )

    @staticmethod
    def _strip_thinking(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S).strip()

    @classmethod
    def _extract_json_text(cls, text: str) -> str:
        text = cls._strip_thinking(text)
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.I | re.S)
        if fence:
            text = fence.group(1).strip()

        # Prefer an object, because all current structured outputs are BaseModel
        # objects rather than top-level arrays.
        obj_start = text.find("{")
        obj_end = text.rfind("}")
        if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
            return text[obj_start : obj_end + 1]

        arr_start = text.find("[")
        arr_end = text.rfind("]")
        if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
            return text[arr_start : arr_end + 1]

        return text.strip()

    @classmethod
    def _parse_structured(
        cls,
        text: str,
        output_schema: Type[BaseModel],
        provider_name: str,
        model_name: str,
    ) -> Any:
        try:
            data = json.loads(cls._extract_json_text(text))
            return output_schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning(
                "[%s] Could not parse structured output as %s: %s",
                provider_name,
                output_schema.__name__,
                exc,
            )
            return LLMTextResponse(
                content=text,
                provider=provider_name,
                model=model_name,
            )


class GeminiProvider(LLMProvider):
    """Google Gemini provider through langchain-google-genai."""

    name = "gemini"

    def __init__(self, model: str, temperature: float, timeout: int):
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self._llm: Optional[ChatGoogleGenerativeAI] = None

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        if not settings.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is required for GeminiProvider.")
        if self._llm is None:
            self._llm = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=self.temperature,
                request_timeout=self.timeout,
                max_output_tokens=8192,
            )
        return self._llm

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Optional[Type[BaseModel]] = None,
    ) -> Any:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        if output_schema is not None:
            return self.llm.with_structured_output(output_schema).invoke(messages)
        return self.llm.invoke(messages)


class OllamaProvider(LLMProvider):
    """Local Ollama provider using its HTTP API."""

    name = "ollama"

    def __init__(self, model: str, temperature: float, timeout: int):
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Optional[Type[BaseModel]] = None,
    ) -> Any:
        if output_schema is not None:
            system_prompt += self._schema_instruction(output_schema)

        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "think": getattr(settings, "OLLAMA_THINK", False),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": self.temperature},
        }
        if output_schema is not None:
            payload["format"] = "json"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        content = data.get("message", {}).get("content", "") or data.get("response", "")
        if output_schema is not None:
            return self._parse_structured(content, output_schema, self.name, self.model)
        return LLMTextResponse(content=content.strip(), provider=self.name, model=self.model)


class OpenAICompatibleProvider(LLMProvider):
    """Provider for local OpenAI-compatible servers such as LM Studio."""

    name = "openai_compatible"

    def __init__(self, model: str, temperature: float, timeout: int):
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.base_url = settings.OPENAI_COMPATIBLE_BASE_URL.rstrip("/")
        self.api_key = settings.OPENAI_COMPATIBLE_API_KEY

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Optional[Type[BaseModel]] = None,
    ) -> Any:
        if output_schema is not None:
            system_prompt += self._schema_instruction(output_schema)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if output_schema is not None:
            payload["response_format"] = {"type": "json_object"}

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if output_schema is not None:
            return self._parse_structured(content, output_schema, self.name, self.model)
        return LLMTextResponse(content=content.strip(), provider=self.name, model=self.model)


def normalise_provider_name(provider_name: str) -> str:
    """Normalise provider aliases used in env vars."""
    name = (provider_name or "gemini").strip().lower().replace("-", "_")
    aliases = {
        "local": "ollama",
        "lmstudio": "openai_compatible",
        "lm_studio": "openai_compatible",
        "openai": "openai_compatible",
    }
    return aliases.get(name, name)


def build_provider(provider_name: str, agent_model: str, temperature: float, timeout: int) -> LLMProvider:
    """Construct a provider adapter from settings/env configuration."""
    provider_name = normalise_provider_name(provider_name)

    if provider_name == "gemini":
        model = agent_model or settings.GEMINI_MODEL
        return GeminiProvider(model=model, temperature=temperature, timeout=timeout)

    if provider_name == "ollama":
        model = agent_model or settings.OLLAMA_MODEL
        return OllamaProvider(model=model, temperature=temperature, timeout=timeout)

    if provider_name == "openai_compatible":
        model = agent_model or settings.OPENAI_COMPATIBLE_MODEL
        return OpenAICompatibleProvider(model=model, temperature=temperature, timeout=timeout)

    raise ValueError(f"Unsupported LLM provider: {provider_name}")
