from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import urlparse

import httpx

from prreviewbot.core.errors import AuthRequiredError, ProviderError
from prreviewbot.core.link_parser import parse_pr_link
from prreviewbot.core.types import ChangedFile, ExistingDiscussionComment, PullRequestInfo
from prreviewbot.providers.base import Provider, ProviderContext


class GiteaProvider(Provider):
    """
    Supports self-hosted Gitea PRs:
      https://gitea.host/owner/repo/pulls/123
    """

    def name(self) -> str:
        return "gitea"

    def fetch_pr(self, ctx: ProviderContext) -> PullRequestInfo:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "gitea" or not parsed.owner or not parsed.repo or not parsed.pr_number:
            raise ProviderError("Invalid Gitea PR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        api_base = f"{u.scheme}://{host}/api/v1"

        if not ctx.token:
            raise AuthRequiredError("gitea", host, "Gitea token required for this PR/repo.")

        headers = {"Authorization": f"token {ctx.token}"}

        with self._client(ctx) as client:
            pr = _get_json(client, f"{api_base}/repos/{parsed.owner}/{parsed.repo}/pulls/{parsed.pr_number}", headers=headers)
            # Prefer diff endpoint when available
            diff_text = _get_text(
                client, f"{api_base}/repos/{parsed.owner}/{parsed.repo}/pulls/{parsed.pr_number}.diff", headers=headers
            )
            comments = _get_json(
                client,
                f"{api_base}/repos/{parsed.owner}/{parsed.repo}/issues/{parsed.pr_number}/comments",
                headers=headers,
            )

        per_file = _split_unified_diff(diff_text)
        changed: List[ChangedFile] = []
        if per_file:
            for path, patch in per_file.items():
                changed.append(ChangedFile(path=path, patch=patch))
        else:
            changed = [ChangedFile(path="(diff)", patch=diff_text)]

        existing: List[ExistingDiscussionComment] = []
        for c in (comments or []):
            existing.append(
                ExistingDiscussionComment(
                    author=((c.get("user") or {}).get("login") or ""),
                    body=c.get("body") or "",
                    url=c.get("html_url"),
                    created_at=c.get("created_at"),
                    kind="comment",
                )
            )

        return PullRequestInfo(
            provider="gitea",
            host=host,
            pr_url=ctx.pr_url,
            title=pr.get("title") or "",
            description=pr.get("body") or "",
            changed_files=changed,
            existing_discussion=existing,
            raw={"pr": pr, "files_count": len(changed), "comments_count": len(existing)},
        )

    def post_comment(self, ctx: ProviderContext, *, body_markdown: str) -> str:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "gitea" or not parsed.owner or not parsed.repo or not parsed.pr_number:
            raise ProviderError("Invalid Gitea PR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        api_base = f"{u.scheme}://{host}/api/v1"
        if not ctx.token:
            raise AuthRequiredError("gitea", host, "Gitea token required to post PR comments.")
        headers = {"Authorization": f"token {ctx.token}"}

        with self._client(ctx) as client:
            # In Gitea, PRs are issues; PR number is the index.
            url = f"{api_base}/repos/{parsed.owner}/{parsed.repo}/issues/{parsed.pr_number}/comments"
            r = client.post(url, headers=headers, json={"body": body_markdown})
            if r.status_code in {401, 403}:
                raise AuthRequiredError("gitea", host, f"Gitea auth failed ({r.status_code}).")
            if r.status_code >= 400:
                raise ProviderError(f"Gitea comment API error {r.status_code}: {r.text[:500]}")
            j = r.json()
            return j.get("html_url") or ""


def _split_unified_diff(diff_text: str) -> Dict[str, str]:
    blocks: Dict[str, List[str]] = {}
    current_path = None
    for line in diff_text.splitlines():
        m = re.match(r"^diff --git a/(.+?) b/(.+?)$", line)
        if m:
            current_path = m.group(2)
            blocks.setdefault(current_path, []).append(line)
            continue
        if current_path is not None:
            blocks[current_path].append(line)
    return {k: "\n".join(v) + "\n" for k, v in blocks.items()}


def _get_json(client: httpx.Client, url: str, *, headers: dict) -> dict:
    r = client.get(url, headers=headers)
    if r.status_code in {401, 403}:
        raise AuthRequiredError("gitea", urlparse(url).netloc, f"Gitea auth failed ({r.status_code}).")
    if r.status_code >= 400:
        raise ProviderError(f"Gitea API error {r.status_code}: {r.text[:500]}")
    return r.json()


def _get_text(client: httpx.Client, url: str, *, headers: dict) -> str:
    r = client.get(url, headers=headers)
    if r.status_code in {401, 403}:
        raise AuthRequiredError("gitea", urlparse(url).netloc, f"Gitea auth failed ({r.status_code}).")
    if r.status_code >= 400:
        raise ProviderError(f"Gitea diff error {r.status_code}: {r.text[:500]}")
    return r.text


