import respx

from prreviewbot.providers.github import GitHubProvider
from prreviewbot.providers.base import ProviderContext


@respx.mock
def test_github_provider_fetch_pr():
    respx.get("https://api.github.com/repos/acme/repo/pulls/1").respond(
        200, json={"title": "T", "body": "B"}
    )
    respx.get("https://api.github.com/repos/acme/repo/pulls/1/files").respond(
        200, json=[{"filename": "a.py", "patch": "@@ -1 +1 @@\n-print(1)\n+print(2)\n"}]
    )
    respx.get("https://api.github.com/repos/acme/repo/issues/1/comments").respond(200, json=[])
    respx.get("https://api.github.com/repos/acme/repo/pulls/1/comments").respond(200, json=[])

    p = GitHubProvider()
    info = p.fetch_pr(
        ProviderContext(
            pr_url="https://github.com/acme/repo/pull/1",
            token="ghp_xxx",
        )
    )
    assert info.title == "T"
    assert info.changed_files[0].path == "a.py"


