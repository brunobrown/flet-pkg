"""LLM provider factory with lazy imports.

Creates pydantic-ai model instances from AIConfig. All pydantic-ai imports
are deferred so that non-AI users are never affected by missing dependencies.
"""

from typing import Any

from flet_pkg.core.ai.config import AIConfig


def create_model(config: AIConfig) -> Any:
    """Create a pydantic-ai model from the given configuration.

    Args:
        config: AI configuration with provider, model, and API key.

    Returns:
        A pydantic-ai model instance.

    Raises:
        ImportError: If pydantic-ai is not installed.
        ValueError: If the provider is not supported.
    """
    try:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.models.openai import OpenAIChatModel
    except ImportError:
        raise ImportError("AI refinement requires pydantic-ai. Install with: uv add flet-pkg[ai]")

    if config.provider == "anthropic":
        return AnthropicModel(config.model)

    if config.provider == "openai":
        return OpenAIChatModel(config.model)

    if config.provider == "google":
        try:
            from pydantic_ai.models.google import GoogleModel

            return GoogleModel(config.model)
        except ImportError:
            raise ImportError(
                "Google AI provider requires google-genai. Install with: uv add pydantic-ai[google]"
            )

    if config.provider == "ollama":
        from pydantic_ai.providers.ollama import OllamaProvider

        return OpenAIChatModel(
            config.model,
            provider=OllamaProvider(base_url=config.base_url),
        )

    raise ValueError(f"Unsupported AI provider: {config.provider}")
