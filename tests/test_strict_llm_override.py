import pytest

from prreviewbot.core.errors import PRReviewBotError
from prreviewbot.core.review_service import ReviewService
from prreviewbot.core.types import ChangedFile, PullRequestInfo
from prreviewbot.storage.config import AppConfig


def test_strict_openai_missing_key_errors(monkeypatch):
    def fake_fetch(self, pr_link: str):
        return PullRequestInfo(
            provider="github",
            host="github.com",
            pr_url=pr_link,
            title="t",
            description="d",
            changed_files=[ChangedFile(path="a.py", patch="")],
        )

    monkeypatch.setattr(ReviewService, "fetch_pr", fake_fetch)

    svc = ReviewService.from_config(AppConfig(llm={"provider": "heuristic"}))
    with pytest.raises(PRReviewBotError) as e:
        svc.review(pr_link="x", llm_provider="openai", llm_model="gpt-4o-mini")
    assert "no api key" in str(e.value).lower()


def test_strict_openai_missing_dependency_errors(monkeypatch):
    # Force openai import to fail
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ModuleNotFoundError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    def fake_fetch(self, pr_link: str):
        return PullRequestInfo(
            provider="github",
            host="github.com",
            pr_url=pr_link,
            title="t",
            description="d",
            changed_files=[ChangedFile(path="a.py", patch="")],
        )

    monkeypatch.setattr(ReviewService, "fetch_pr", fake_fetch)

    svc = ReviewService.from_config(AppConfig(llm={"provider": "openai", "openai_api_key": "k"}))
    with pytest.raises(PRReviewBotError) as e:
        svc.review(pr_link="x", llm_provider="openai", llm_model="gpt-4o-mini")
    assert "not installed" in str(e.value).lower()


