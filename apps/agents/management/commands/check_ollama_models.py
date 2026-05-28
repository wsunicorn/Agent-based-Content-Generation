"""Check whether the Ollama models required by agent routing are installed."""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.agents.llm_providers import normalise_provider_name


class Command(BaseCommand):
    help = "List installed and missing Ollama models needed by the configured agents."

    def handle(self, *args, **options):
        required = self._required_models()
        installed = self._installed_models()
        installed_aliases = self._with_latest_aliases(installed)
        missing = sorted(required - installed_aliases)
        present = sorted(required & installed_aliases)

        self.stdout.write(self.style.MIGRATE_HEADING("=== Ollama model check ==="))
        self.stdout.write(f"Base URL : {settings.OLLAMA_BASE_URL}")
        self.stdout.write("")

        if present:
            self.stdout.write(self.style.SUCCESS("Installed:"))
            for model in present:
                self.stdout.write(f"  - {model}")
        else:
            self.stdout.write("Installed: none of the configured models")

        self.stdout.write("")
        if missing:
            self.stdout.write(self.style.WARNING("Missing:"))
            for model in missing:
                self.stdout.write(f"  - {model}")
            self.stdout.write("")
            self.stdout.write("Pull commands:")
            for model in missing:
                self.stdout.write(f"  ollama pull {model}")
        else:
            self.stdout.write(self.style.SUCCESS("All configured Ollama models are installed."))

    def _required_models(self) -> set[str]:
        required = set(getattr(settings, "OLLAMA_REQUIRED_MODELS", []))
        required.add(settings.OLLAMA_MODEL)

        provider_map = getattr(settings, "LLM_AGENT_PROVIDERS", {})
        agent_models = getattr(settings, "LLM_AGENT_MODELS", {})
        default_provider = normalise_provider_name(getattr(settings, "LOCAL_LLM_PROVIDER", "ollama"))

        for agent, model in agent_models.items():
            provider = normalise_provider_name(provider_map.get(agent, default_provider))
            if provider == "ollama" and model:
                required.add(model)

        for name in (
            "OLLAMA_FAST_MODEL",
            "OLLAMA_REASONING_MODEL",
            "OLLAMA_STRUCTURED_MODEL",
            "OLLAMA_EMBED_MODEL",
            "OLLAMA_VISION_MODEL",
        ):
            model = getattr(settings, name, "")
            if model:
                required.add(model)

        return {model for model in required if model}

    def _installed_models(self) -> set[str]:
        import httpx

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Could not reach Ollama at {url}: {exc}"))
            return set()

        data = response.json()
        return {
            model.get("name") or model.get("model")
            for model in data.get("models", [])
            if model.get("name") or model.get("model")
        }

    @staticmethod
    def _with_latest_aliases(models: set[str]) -> set[str]:
        aliases = set(models)
        for model in models:
            if model.endswith(":latest"):
                aliases.add(model.removesuffix(":latest"))
            elif ":" not in model:
                aliases.add(f"{model}:latest")
        return aliases
