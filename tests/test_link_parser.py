import pytest

from prreviewbot.core.link_parser import parse_pr_link


@pytest.mark.parametrize(
    "url,provider",
    [
        ("https://github.com/acme/repo/pull/123", "github"),
        ("https://gitea.example.com/acme/repo/pulls/123", "gitea"),
        ("https://gitlab.com/acme/repo/-/merge_requests/7", "gitlab"),
        ("https://bitbucket.org/acme/repo/pull-requests/9", "bitbucket"),
        ("https://dev.azure.com/org/proj/_git/repo/pullrequest/42", "azure"),
        ("https://org.visualstudio.com/proj/_git/repo/pullrequest/42", "azure"),
    ],
)
def test_parse_pr_link(url, provider):
    p = parse_pr_link(url)
    assert p.provider == provider


def test_parse_pr_link_unsupported():
    with pytest.raises(ValueError):
        parse_pr_link("https://example.com/something")


