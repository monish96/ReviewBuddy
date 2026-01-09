import json

import pytest
from fastapi.testclient import TestClient

from prreviewbot.storage.config import AppConfig
from prreviewbot.web.app import create_app


@pytest.fixture()
def client(tmp_path):
    # use temp config dir
    app = create_app(data_dir=tmp_path)
    return TestClient(app)


def test_settings_roundtrip(client):
    r = client.post("/api/settings/token", json={"provider": "github", "host": "github.com", "token": "abc123"})
    assert r.status_code == 200

    s = client.get("/api/settings").json()
    assert "github" in s["tokens"]
    assert "github.com" in s["tokens"]["github"]

def test_settings_host_normalization(client):
    r = client.post(
        "/api/settings/token",
        json={"provider": "azure", "host": "https://dev.azure.com/some/path", "token": "pat"},
    )
    assert r.status_code == 200
    assert r.json()["host"] == "dev.azure.com"

    s = client.get("/api/settings").json()
    assert "dev.azure.com" in s["tokens"]["azure"]

def test_delete_token(client):
    client.post("/api/settings/token", json={"provider": "github", "host": "github.com", "token": "abc123"})
    r = client.post("/api/settings/token/delete", json={"provider": "github", "host": "github.com"})
    assert r.status_code == 200
    s = client.get("/api/settings").json()
    assert "github" not in s["tokens"]


def test_review_requires_auth(client, monkeypatch):
    # Patch review service to always raise AuthRequiredError to validate API shape
    from prreviewbot.core.errors import AuthRequiredError
    from prreviewbot.core.review_service import ReviewService

    def boom(self, *, pr_link: str, language=None, **_kwargs):
        raise AuthRequiredError("github", "github.com", "token required")

    monkeypatch.setattr(ReviewService, "review", boom)

    r = client.post(
        "/api/review",
        json={"pr_link": "https://github.com/a/b/pull/1", "language": None, "llm_provider": "heuristic", "llm_model": None},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["provider"] == "github"
    assert body["detail"]["host"] == "github.com"


