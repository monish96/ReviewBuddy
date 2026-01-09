from __future__ import annotations

from typing import List
from urllib.parse import quote, urlparse

import httpx

from prreviewbot.core.errors import AuthRequiredError, ProviderError
from prreviewbot.core.link_parser import parse_pr_link
from prreviewbot.core.types import ChangedFile, ExistingDiscussionComment, PullRequestInfo
from prreviewbot.providers.base import Provider, ProviderContext


class GitLabProvider(Provider):
    def name(self) -> str:
        return "gitlab"

    def fetch_pr(self, ctx: ProviderContext) -> PullRequestInfo:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "gitlab" or not parsed.namespace_path or not parsed.pr_number:
            raise ProviderError("Invalid GitLab MR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        api_base = f"{u.scheme}://{host}/api/v4"

        if not ctx.token:
            raise AuthRequiredError("gitlab", host, "GitLab token required for this MR/project.")

        headers = {"PRIVATE-TOKEN": ctx.token}
        project_id = quote(parsed.namespace_path, safe="")

        with self._client(ctx) as client:
            mr = _get_json(client, f"{api_base}/projects/{project_id}/merge_requests/{parsed.pr_number}", headers=headers)
            changes = _get_json(
                client,
                f"{api_base}/projects/{project_id}/merge_requests/{parsed.pr_number}/changes",
                headers=headers,
            )
            notes = _get_json(
                client,
                f"{api_base}/projects/{project_id}/merge_requests/{parsed.pr_number}/notes",
                headers=headers,
            )

        changed: List[ChangedFile] = []
        for c in changes.get("changes", []) or []:
            changed.append(ChangedFile(path=c.get("new_path") or c.get("old_path") or "unknown", patch=c.get("diff")))

        existing: List[ExistingDiscussionComment] = []
        for n in (notes or []):
            existing.append(
                ExistingDiscussionComment(
                    author=((n.get("author") or {}).get("username") or (n.get("author") or {}).get("name") or ""),
                    body=n.get("body") or "",
                    url=n.get("web_url") or n.get("url"),
                    created_at=n.get("created_at"),
                    kind="comment",
                )
            )

        return PullRequestInfo(
            provider="gitlab",
            host=host,
            pr_url=ctx.pr_url,
            title=mr.get("title") or "",
            description=mr.get("description") or "",
            changed_files=changed,
            existing_discussion=existing,
            raw={"mr": mr, "changes_count": len(changed), "notes_count": len(existing)},
        )

    def post_comment(self, ctx: ProviderContext, *, body_markdown: str) -> str:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "gitlab" or not parsed.namespace_path or not parsed.pr_number:
            raise ProviderError("Invalid GitLab MR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        api_base = f"{u.scheme}://{host}/api/v4"
        if not ctx.token:
            raise AuthRequiredError("gitlab", host, "GitLab token required to post MR comments.")
        headers = {"PRIVATE-TOKEN": ctx.token}
        project_id = quote(parsed.namespace_path, safe="")

        with self._client(ctx) as client:
            url = f"{api_base}/projects/{project_id}/merge_requests/{parsed.pr_number}/notes"
            r = client.post(url, headers=headers, json={"body": body_markdown})
            if r.status_code in {401, 403}:
                raise AuthRequiredError("gitlab", host, f"GitLab auth failed ({r.status_code}).")
            if r.status_code >= 400:
                raise ProviderError(f"GitLab comment API error {r.status_code}: {r.text[:500]}")
            j = r.json()
            return j.get("web_url") or j.get("url") or ""


def _get_json(client: httpx.Client, url: str, *, headers: dict) -> dict:
    r = client.get(url, headers=headers)
    if r.status_code in {401, 403}:
        raise AuthRequiredError("gitlab", urlparse(url).netloc, f"GitLab auth failed ({r.status_code}).")
    if r.status_code >= 400:
        raise ProviderError(f"GitLab API error {r.status_code}: {r.text[:500]}")
    return r.json()


