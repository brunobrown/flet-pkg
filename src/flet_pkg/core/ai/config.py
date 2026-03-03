"""AI refinement configuration.

Loads settings from CLI flags, environment variables, or provider defaults.
Priority: CLI flags > env vars > provider defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Provider → (default model, env var for API key)
_PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {
    "anthropic": ("claude-sonnet-4-6", "ANTHROPIC_API_KEY"),
    "openai": ("gpt-4.1-mini", "OPENAI_API_KEY"),
    "google": ("gemini-2.5-flash", "GOOGLE_API_KEY"),
    "ollama": ("qwen2.5-coder", ""),
}


@dataclass
class AIConfig:
    """Configuration for the AI refinement pipeline."""

    provider: str = "ollama"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.1
    max_tokens: int = 4096

    @classmethod
    def load(
        cls,
        provider: str | None = None,
        model: str | None = None,
    ) -> AIConfig:
        """Load configuration from CLI flags and environment variables.

        Args:
            provider: Provider name (anthropic, openai, google, ollama).
            model: Model name override.

        Returns:
            Populated AIConfig instance.
        """
        # Determine provider
        resolved_provider = provider or os.environ.get("FLET_PKG_AI_PROVIDER", "ollama")
        if resolved_provider not in _PROVIDER_DEFAULTS:
            resolved_provider = "ollama"

        default_model, env_key = _PROVIDER_DEFAULTS[resolved_provider]

        # Determine model
        resolved_model = model or os.environ.get("FLET_PKG_AI_MODEL", "") or default_model

        # Determine API key
        api_key = ""
        if env_key:
            api_key = os.environ.get(env_key, "")

        # Ollama base URL
        base_url = ""
        if resolved_provider == "ollama":
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")

        return cls(
            provider=resolved_provider,
            model=resolved_model,
            api_key=api_key,
            base_url=base_url,
        )

    def is_available(self) -> bool:
        """Check if the provider is configured and usable."""
        if self.provider == "ollama":
            return True
        return bool(self.api_key)
