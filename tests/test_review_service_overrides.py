from prreviewbot.core.review_service import ReviewService
from prreviewbot.storage.config import AppConfig


def test_review_service_uses_request_override_provider(monkeypatch):
    # Avoid real provider calls
    from prreviewbot.core.types import PullRequestInfo, ChangedFile

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

    cfg = AppConfig(llm={"provider": "heuristic"})
    svc = ReviewService.from_config(cfg)
    res = svc.review(pr_link="x", llm_provider="heuristic", llm_model=None)
    assert res.model == "heuristic"


