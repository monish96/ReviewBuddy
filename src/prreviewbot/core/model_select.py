from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ModelChoice:
    provider: str  # heuristic|openai
    model: str


DEFAULT_LANGUAGE_MODEL_MAP: Dict[str, ModelChoice] = {
    # Reasonable defaults; can be overridden in Settings.
    "python": ModelChoice(provider="openai", model="gpt-4o-mini"),
    "typescript": ModelChoice(provider="openai", model="gpt-4o-mini"),
    "javascript": ModelChoice(provider="openai", model="gpt-4o-mini"),
    "java": ModelChoice(provider="openai", model="gpt-4o-mini"),
    "go": ModelChoice(provider="openai", model="gpt-4o-mini"),
    "rust": ModelChoice(provider="openai", model="gpt-4o-mini"),
    "csharp": ModelChoice(provider="openai", model="gpt-4o-mini"),
    "cpp": ModelChoice(provider="openai", model="gpt-4o-mini"),
    "general": ModelChoice(provider="heuristic", model="heuristic"),
}


def choose_model(
    *,
    language: str,
    llm_provider: str,
    llm_default_model: Optional[str],
    overrides: Dict[str, Dict[str, str]],
) -> ModelChoice:
    lang = language.lower()

    if lang in overrides:
        o = overrides[lang]
        return ModelChoice(provider=o.get("provider", llm_provider), model=o.get("model", llm_default_model or ""))

    # Respect the active provider. Language mapping primarily influences the model/deployment name.
    if lang in DEFAULT_LANGUAGE_MODEL_MAP:
        default = DEFAULT_LANGUAGE_MODEL_MAP[lang]
        if llm_provider in {"openai", "azure_openai"}:
            return ModelChoice(provider=llm_provider, model=llm_default_model or default.model)
        return ModelChoice(provider="heuristic", model="heuristic")

    if llm_provider in {"openai", "azure_openai"}:
        return ModelChoice(provider=llm_provider, model=llm_default_model or "gpt-4o-mini")
    return ModelChoice(provider="heuristic", model="heuristic")


