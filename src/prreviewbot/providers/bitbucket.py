from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import urlparse

import httpx

from prreviewbot.core.errors import AuthRequiredError, ProviderError
from prreviewbot.core.link_parser import parse_pr_link
from prreviewbot.core.types import ChangedFile, ExistingDiscussionComment, PullRequestInfo
from prreviewbot.providers.base import Provider, ProviderContext


class BitbucketCloudProvider(Provider):
    def name(self) -> str:
        return "bitbucket"

    def fetch_pr(self, ctx: ProviderContext) -> PullRequestInfo:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "bitbucket" or not parsed.workspace or not parsed.repo or not parsed.pr_number:
            raise ProviderError("Invalid Bitbucket Cloud PR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        if not host.endswith("bitbucket.org"):
            raise ProviderError("Bitbucket Server/Data Center is not supported in this MVP (Bitbucket Cloud only).")
        api_base = "https://api.bitbucket.org/2.0"

        if not ctx.token:
            raise AuthRequiredError(
                "bitbucket",
                host,
                "Bitbucket app password required. Use username:app_password as the token value.",
            )

        # Bitbucket Cloud uses Basic Auth; token stored as "username:app_password"
        headers = {}
        auth = tuple(ctx.token.split(":", 1)) if ":" in ctx.token else None
        if not auth:
            raise ProviderError("Bitbucket token must be in form username:app_password")

        with self._client(ctx) as client:
            pr = _get_json(
                client,
                f"{api_base}/repositories/{parsed.workspace}/{parsed.repo}/pullrequests/{parsed.pr_number}",
                headers=headers,
                auth=auth,
            )
            diffstat = _get_json(
                client,
                f"{api_base}/repositories/{parsed.workspace}/{parsed.repo}/pullrequests/{parsed.pr_number}/diffstat",
                headers=headers,
                auth=auth,
            )
            diff_text = _get_text(
                client,
                f"{api_base}/repositories/{parsed.workspace}/{parsed.repo}/pullrequests/{parsed.pr_number}/diff",
                headers=headers,
                auth=auth,
            )
            comments = _get_json(
                client,
                f"{api_base}/repositories/{parsed.workspace}/{parsed.repo}/pullrequests/{parsed.pr_number}/comments",
                headers=headers,
                auth=auth,
            )

        file_paths = _extract_paths(diffstat)
        per_file = _split_unified_diff(diff_text)
        changed: List[ChangedFile] = []
        for p in file_paths:
            changed.append(ChangedFile(path=p, patch=per_file.get(p)))
        if not changed:
            changed = [ChangedFile(path="(diff)", patch=diff_text)]

        existing: List[ExistingDiscussionComment] = []
        for c in (comments.get("values") or []) if isinstance(comments, dict) else []:
            existing.append(
                ExistingDiscussionComment(
                    author=((c.get("user") or {}).get("nickname") or (c.get("user") or {}).get("display_name") or ""),
                    body=((c.get("content") or {}).get("raw") if isinstance(c.get("content"), dict) else "") or "",
                    url=((c.get("links") or {}).get("html") or {}).get("href") if isinstance(c.get("links"), dict) else None,
                    created_at=c.get("created_on"),
                    kind="comment",
                )
            )

        return PullRequestInfo(
            provider="bitbucket",
            host=host,
            pr_url=ctx.pr_url,
            title=pr.get("title") or "",
            description=pr.get("description") or "",
            changed_files=changed,
            existing_discussion=existing,
            raw={"pr": pr, "files_count": len(changed), "comments_count": len(existing)},
        )

    def post_comment(self, ctx: ProviderContext, *, body_markdown: str) -> str:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "bitbucket" or not parsed.workspace or not parsed.repo or not parsed.pr_number:
            raise ProviderError("Invalid Bitbucket Cloud PR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        if not host.endswith("bitbucket.org"):
            raise ProviderError("Bitbucket Server/Data Center is not supported in this MVP (Bitbucket Cloud only).")
        api_base = "https://api.bitbucket.org/2.0"
        if not ctx.token:
            raise AuthRequiredError(
                "bitbucket",
                host,
                "Bitbucket app password required to post comments. Use username:app_password as the token value.",
            )
        auth = tuple(ctx.token.split(":", 1)) if ":" in ctx.token else None
        if not auth:
            raise ProviderError("Bitbucket token must be in form username:app_password")

        with self._client(ctx) as client:
            url = f"{api_base}/repositories/{parsed.workspace}/{parsed.repo}/pullrequests/{parsed.pr_number}/comments"
            r = client.post(url, auth=auth, json={"content": {"raw": body_markdown}})
            if r.status_code in {401, 403}:
                raise AuthRequiredError("bitbucket", host, f"Bitbucket auth failed ({r.status_code}).")
            if r.status_code >= 400:
                raise ProviderError(f"Bitbucket comment API error {r.status_code}: {r.text[:500]}")
            j = r.json()
            links = j.get("links") or {}
            return (links.get("html") or {}).get("href") or (links.get("self") or {}).get("href") or ""


def _extract_paths(diffstat_json: dict) -> List[str]:
    out: List[str] = []
    for v in diffstat_json.get("values", []) or []:
        newp = ((v.get("new") or {}).get("path")) if isinstance(v.get("new"), dict) else None
        oldp = ((v.get("old") or {}).get("path")) if isinstance(v.get("old"), dict) else None
        out.append(newp or oldp or "unknown")
    # de-dupe preserving order
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _split_unified_diff(diff_text: str) -> Dict[str, str]:
    """
    Best-effort split by `diff --git a/... b/...` blocks.
    """
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


def _get_json(client: httpx.Client, url: str, *, headers: dict, auth) -> dict:
    r = client.get(url, headers=headers, auth=auth)
    if r.status_code in {401, 403}:
        raise AuthRequiredError("bitbucket", urlparse(url).netloc, f"Bitbucket auth failed ({r.status_code}).")
    if r.status_code >= 400:
        raise ProviderError(f"Bitbucket API error {r.status_code}: {r.text[:500]}")
    return r.json()


def _get_text(client: httpx.Client, url: str, *, headers: dict, auth) -> str:
    r = client.get(url, headers=headers, auth=auth)
    if r.status_code in {401, 403}:
        raise AuthRequiredError("bitbucket", urlparse(url).netloc, f"Bitbucket auth failed ({r.status_code}).")
    if r.status_code >= 400:
        raise ProviderError(f"Bitbucket diff error {r.status_code}: {r.text[:500]}")
    return r.text


