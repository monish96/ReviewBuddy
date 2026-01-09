from prreviewbot.core.review_service import ReviewService
from prreviewbot.storage.config import AppConfig


def test_review_service_azure_openai_missing_openai_falls_back(monkeypatch):
    # Force openai import to fail
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ModuleNotFoundError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    cfg = AppConfig(
        llm={
            "provider": "openai",
            "openai_endpoint": "https://genai-nexus.api.corpinter.net/apikey/",
            "openai_api_version": "2024-02-15-preview",
            "openai_deployment": "gpt-4o-mini",
            "openai_api_key": "k",
        }
    )
    svc = ReviewService.from_config(cfg)
    llm = svc._build_llm("openai", "gpt-4o-mini")
    assert llm.name() == "heuristic"


