from __future__ import annotations

from typing import List
from urllib.parse import urlparse

import httpx

from prreviewbot.core.errors import AuthRequiredError, ProviderError
from prreviewbot.core.link_parser import parse_pr_link
from prreviewbot.core.types import ChangedFile, ExistingDiscussionComment, PullRequestInfo
from prreviewbot.providers.base import Provider, ProviderContext


class GitHubProvider(Provider):
    def name(self) -> str:
        return "github"

    def fetch_pr(self, ctx: ProviderContext) -> PullRequestInfo:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "github" or not parsed.owner or not parsed.repo or not parsed.pr_number:
            raise ProviderError("Invalid GitHub PR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        api_base = "https://api.github.com" if host == "github.com" else f"{u.scheme}://{host}/api/v3"
        headers = {"Accept": "application/vnd.github+json"}
        if not ctx.token:
            raise AuthRequiredError("github", host, "GitHub token required for this PR/repo.")
        headers["Authorization"] = f"Bearer {ctx.token}"

        with self._client(ctx) as client:
            pr = _get_json(
                client,
                f"{api_base}/repos/{parsed.owner}/{parsed.repo}/pulls/{parsed.pr_number}",
                headers=headers,
            )
            files = _get_all_files(
                client,
                f"{api_base}/repos/{parsed.owner}/{parsed.repo}/pulls/{parsed.pr_number}/files",
                headers=headers,
            )
            # Existing discussion context:
            # - Issue comments (general discussion)
            issue_comments = _get_all(
                client,
                f"{api_base}/repos/{parsed.owner}/{parsed.repo}/issues/{parsed.pr_number}/comments",
                headers=headers,
            )
            # - Review comments (inline comments)
            review_comments = _get_all(
                client,
                f"{api_base}/repos/{parsed.owner}/{parsed.repo}/pulls/{parsed.pr_number}/comments",
                headers=headers,
            )

        changed: List[ChangedFile] = []
        for f in files:
            changed.append(ChangedFile(path=f.get("filename") or "unknown", patch=f.get("patch")))

        existing: List[ExistingDiscussionComment] = []
        for c in issue_comments:
            existing.append(
                ExistingDiscussionComment(
                    author=((c.get("user") or {}).get("login") or ""),
                    body=c.get("body") or "",
                    url=c.get("html_url") or c.get("url"),
                    created_at=c.get("created_at"),
                    kind="issue_comment",
                )
            )
        for c in review_comments:
            existing.append(
                ExistingDiscussionComment(
                    author=((c.get("user") or {}).get("login") or ""),
                    body=c.get("body") or "",
                    url=c.get("html_url") or c.get("url"),
                    file_path=c.get("path"),
                    created_at=c.get("created_at"),
                    kind="review_comment",
                )
            )

        return PullRequestInfo(
            provider="github",
            host=host,
            pr_url=ctx.pr_url,
            title=pr.get("title") or "",
            description=pr.get("body") or "",
            changed_files=changed,
            existing_discussion=existing,
            raw={"pr": pr, "files_count": len(files), "issue_comments_count": len(issue_comments), "review_comments_count": len(review_comments)},
        )

    def post_comment(self, ctx: ProviderContext, *, body_markdown: str) -> str:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "github" or not parsed.owner or not parsed.repo or not parsed.pr_number:
            raise ProviderError("Invalid GitHub PR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        api_base = "https://api.github.com" if host == "github.com" else f"{u.scheme}://{host}/api/v3"
        if not ctx.token:
            raise AuthRequiredError("github", host, "GitHub token required to post PR comments.")
        headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {ctx.token}"}

        with self._client(ctx) as client:
            url = f"{api_base}/repos/{parsed.owner}/{parsed.repo}/issues/{parsed.pr_number}/comments"
            r = client.post(url, headers=headers, json={"body": body_markdown})
            if r.status_code in {401, 403}:
                raise AuthRequiredError("github", host, f"GitHub auth failed ({r.status_code}).")
            if r.status_code >= 400:
                raise ProviderError(f"GitHub comment API error {r.status_code}: {r.text[:500]}")
            j = r.json()
            return j.get("html_url") or j.get("url") or ""


def _get_json(client: httpx.Client, url: str, *, headers: dict) -> dict:
    r = client.get(url, headers=headers)
    if r.status_code in {401, 403}:
        raise AuthRequiredError("github", urlparse(url).netloc, f"GitHub auth failed ({r.status_code}).")
    if r.status_code >= 400:
        raise ProviderError(f"GitHub API error {r.status_code}: {r.text[:500]}")
    return r.json()


def _get_all_files(client: httpx.Client, url: str, *, headers: dict) -> list:
    out = []
    page = 1
    while True:
        r = client.get(url, headers=headers, params={"per_page": 100, "page": page})
        if r.status_code in {401, 403}:
            raise AuthRequiredError("github", urlparse(url).netloc, f"GitHub auth failed ({r.status_code}).")
        if r.status_code >= 400:
            raise ProviderError(f"GitHub files API error {r.status_code}: {r.text[:500]}")
        items = r.json()
        if not items:
            break
        out.extend(items)
        if len(items) < 100:
            break
        page += 1
        if page > 20:
            break
    return out


def _get_all(client: httpx.Client, url: str, *, headers: dict) -> list:
    out = []
    page = 1
    while True:
        r = client.get(url, headers=headers, params={"per_page": 100, "page": page})
        if r.status_code in {401, 403}:
            raise AuthRequiredError("github", urlparse(url).netloc, f"GitHub auth failed ({r.status_code}).")
        if r.status_code >= 400:
            raise ProviderError(f"GitHub API error {r.status_code}: {r.text[:500]}")
        items = r.json()
        if not items:
            break
        out.extend(items)
        if len(items) < 100:
            break
        page += 1
        if page > 10:
            break
    return out


