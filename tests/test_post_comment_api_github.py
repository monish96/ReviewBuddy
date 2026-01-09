import respx
from fastapi.testclient import TestClient

from prreviewbot.web.app import create_app


@respx.mock
def test_post_comment_github(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    # save github token
    client.post("/api/settings/token", json={"provider": "github", "host": "github.com", "token": "t"})

    respx.post("https://api.github.com/repos/acme/repo/issues/1/comments").respond(
        201, json={"html_url": "https://github.com/acme/repo/pull/1#issuecomment-1"}
    )

    r = client.post(
        "/api/pr/comment",
        json={
            "pr_link": "https://github.com/acme/repo/pull/1",
            "file_path": "a.py",
            "severity": "warn",
            "message": "m",
            "suggestion": "s",
            "code_example": "```python\nprint('x')\n```",
            "start_line": 12,
            "end_line": 18,
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "issuecomment" in (r.json().get("comment_url") or "")


