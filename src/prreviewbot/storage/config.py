from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from prreviewbot.core.host import normalize_host


def default_data_dir() -> Path:
    return Path.home() / ".prreviewbot"


@dataclass
class AppConfig:
    # auth tokens keyed by provider + host
    tokens: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # LLM provider config (optional)
    llm: Dict[str, Any] = field(default_factory=dict)
    # per-language model mapping override
    model_map: Dict[str, Dict[str, str]] = field(default_factory=dict)


class ConfigStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or default_data_dir()
        self.path = self.data_dir / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        cfg = AppConfig(
            tokens=data.get("tokens", {}) or {},
            llm=data.get("llm", {}) or {},
            model_map=data.get("model_map", {}) or {},
        )
        # Migration: normalize provider keys + host keys so pasted URLs like "https://dev.azure.com" don't
        # create confusing duplicates and don't break token lookup.
        migrated_tokens = _migrate_tokens(cfg.tokens)
        migrated_llm = _migrate_llm(cfg.llm)
        if migrated_tokens is not None:
            cfg.tokens = migrated_tokens
        if migrated_llm is not None:
            cfg.llm = migrated_llm
        if migrated_tokens is not None or migrated_llm is not None:
            # Persist migration so UI doesn't keep showing duplicates / old keys.
            self.save(cfg)
        return cfg

    def save(self, cfg: AppConfig) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(
                {"tokens": cfg.tokens, "llm": cfg.llm, "model_map": cfg.model_map},
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except Exception:
            # best-effort on platforms that don't support chmod in the same way
            pass


def _migrate_tokens(tokens: Dict[str, Dict[str, str]]) -> Optional[Dict[str, Dict[str, str]]]:
    if not tokens:
        return None

    changed = False
    new_tokens: Dict[str, Dict[str, str]] = {}
    # provider key normalization
    for provider_key, hosts in (tokens or {}).items():
        provider = (provider_key or "").strip().lower()
        if provider != provider_key:
            changed = True
        hosts = hosts or {}

        merged: Dict[str, str] = {}
        canonical: Dict[str, bool] = {}
        for host_key, tok in hosts.items():
            nh = normalize_host(host_key)
            if nh != host_key:
                changed = True
            if not nh:
                continue
            is_canonical = (host_key == nh)
            if nh not in merged:
                merged[nh] = tok
                canonical[nh] = is_canonical
            else:
                # Prefer canonical (already-normalized) key if there is a collision.
                if canonical.get(nh) is False and is_canonical is True:
                    merged[nh] = tok
                    canonical[nh] = True
                    changed = True

        if merged:
            new_tokens[provider] = merged
        else:
            if provider in new_tokens:
                changed = True

    if not changed:
        return None
    return new_tokens


def _migrate_llm(llm: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not llm:
        return None
    changed = False
    out = dict(llm)

    # Provider rename (legacy)
    if out.get("provider") in {"azure_openai", "azureopenai"}:
        out["provider"] = "openai"
        changed = True

    # Key renames: azure_openai_* -> openai_*
    if "azure_openai_endpoint" in out and "openai_endpoint" not in out:
        out["openai_endpoint"] = out.get("azure_openai_endpoint")
        changed = True
    if "azure_openai_api_version" in out and "openai_api_version" not in out:
        out["openai_api_version"] = out.get("azure_openai_api_version")
        changed = True
    if "azure_openai_deployment" in out and "openai_deployment" not in out:
        out["openai_deployment"] = out.get("azure_openai_deployment")
        changed = True
    if "azure_openai_api_key" in out and "openai_api_key" not in out:
        out["openai_api_key"] = out.get("azure_openai_api_key")
        changed = True

    # Drop legacy keys to reduce confusion
    for k in ["azure_openai_endpoint", "azure_openai_api_version", "azure_openai_deployment", "azure_openai_api_key"]:
        if k in out:
            del out[k]
            changed = True

    return out if changed else None


