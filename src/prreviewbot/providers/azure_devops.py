from __future__ import annotations

import difflib
from typing import List, Optional
from urllib.parse import quote, urlencode, urlparse, unquote

import httpx
import json

from prreviewbot.core.errors import AuthRequiredError, ProviderError
from prreviewbot.core.link_parser import parse_pr_link
from prreviewbot.core.types import ChangedFile, ExistingDiscussionComment, PullRequestInfo
from prreviewbot.providers.base import Provider, ProviderContext


class AzureDevOpsProvider(Provider):
    def name(self) -> str:
        return "azure"

    def fetch_pr(self, ctx: ProviderContext) -> PullRequestInfo:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "azure" or not parsed.org or not parsed.project or not parsed.repo or not parsed.pr_number:
            raise ProviderError("Invalid Azure DevOps PR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        scheme = u.scheme

        org_seg = _enc_seg(parsed.org)
        project_seg = _enc_seg(parsed.project)
        repo_seg = _enc_seg(parsed.repo)

        # Base URL differs between dev.azure.com and *.visualstudio.com
        if host.endswith("dev.azure.com"):
            base = f"{scheme}://{host}/{org_seg}/{project_seg}"
        else:
            # org is subdomain
            base = f"{scheme}://{host}/{project_seg}"

        if not ctx.token:
            raise AuthRequiredError("azure", host, "Azure DevOps PAT required for this PR/repo.")

        headers = {"Accept": "application/json"}
        auth = ("", ctx.token)  # PAT as basic auth password

        pr_api = f"{base}/_apis/git/repositories/{repo_seg}/pullRequests/{parsed.pr_number}"
        pr_url = f"{pr_api}?{urlencode({'api-version': '7.1-preview.1'})}"

        with self._client(ctx) as client:
            pr = _get_json(client, pr_url, headers=headers, auth=auth)

            source_commit = _deep_get(pr, ["lastMergeSourceCommit", "commitId"])
            target_commit = _deep_get(pr, ["lastMergeTargetCommit", "commitId"])
            if not source_commit or not target_commit:
                # fallback fields
                source_commit = _deep_get(pr, ["sourceRefName"]) or source_commit
                target_commit = _deep_get(pr, ["targetRefName"]) or target_commit

            # NOTE: Git PR file changes are exposed via iteration changes, not /pullRequests/{id}/changes.
            # Flow: list iterations -> pick latest -> list changes for that iteration.
            iteration_id = _latest_iteration_id(
                client,
                base=base,
                repo=repo_seg,
                pr_number=parsed.pr_number,
                headers=headers,
                auth=auth,
            )
            iteration_changes = _get_iteration_changes(
                client,
                base=base,
                repo=repo_seg,
                pr_number=parsed.pr_number,
                iteration_id=iteration_id,
                headers=headers,
                auth=auth,
            )

            paths = _extract_paths(iteration_changes)
            changed_files: List[ChangedFile] = []
            for p in paths[:30]:
                patch = None
                if source_commit and target_commit:
                    patch = _compute_file_diff(
                        client,
                        base=base,
                        repo=repo_seg,
                        path=p,
                        base_commit=target_commit,
                        target_commit=source_commit,
                        headers=headers,
                        auth=auth,
                    )
                changed_files.append(ChangedFile(path=p, patch=patch))

            # Existing discussion threads
            threads_url = f"{base}/_apis/git/repositories/{repo_seg}/pullRequests/{parsed.pr_number}/threads?{urlencode({'api-version': '7.1-preview.1'})}"
            threads = _get_json(client, threads_url, headers=headers, auth=auth)
            existing = _extract_threads(threads)

        return PullRequestInfo(
            provider="azure",
            host=host,
            pr_url=ctx.pr_url,
            title=pr.get("title") or "",
            description=pr.get("description") or "",
            changed_files=changed_files,
            existing_discussion=existing,
            raw={"pr": pr, "files_count": len(changed_files), "threads_count": len(existing)},
        )

    def post_comment(self, ctx: ProviderContext, *, body_markdown: str) -> str:
        parsed = parse_pr_link(ctx.pr_url)
        if parsed.provider != "azure" or not parsed.org or not parsed.project or not parsed.repo or not parsed.pr_number:
            raise ProviderError("Invalid Azure DevOps PR link")

        u = urlparse(ctx.pr_url)
        host = u.netloc
        scheme = u.scheme

        org_seg = _enc_seg(parsed.org)
        project_seg = _enc_seg(parsed.project)
        repo_seg = _enc_seg(parsed.repo)

        if host.endswith("dev.azure.com"):
            base = f"{scheme}://{host}/{org_seg}/{project_seg}"
        else:
            base = f"{scheme}://{host}/{project_seg}"

        if not ctx.token:
            raise AuthRequiredError("azure", host, "Azure DevOps PAT required to post PR comments.")
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        auth = ("", ctx.token)

        url = f"{base}/_apis/git/repositories/{repo_seg}/pullRequests/{parsed.pr_number}/threads?{urlencode({'api-version': '7.1-preview.1'})}"
        payload = {
            "comments": [
                {
                    "parentCommentId": 0,
                    "content": body_markdown,
                    "commentType": 1,
                }
            ],
            "status": 1,
        }
        with self._client(ctx) as client:
            r = client.post(url, headers=headers, auth=auth, json=payload)
            if r.status_code in {401, 403}:
                raise AuthRequiredError("azure", host, f"Azure DevOps auth failed ({r.status_code}).")
            if r.status_code >= 400:
                raise ProviderError(f"Azure DevOps comment API error {r.status_code}: {r.text[:500]}")
            j = r.json()
            tid = j.get("id")
            # Best-effort link back to PR (threads deep links differ); returning PR URL is still useful.
            return str(tid) if tid is not None else ctx.pr_url


def _deep_get(d: dict, path: List[str]) -> Optional[str]:
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return str(cur) if cur is not None else None


def _extract_paths(changes_json: dict) -> List[str]:
    out: List[str] = []
    # Iteration changes response includes `changeEntries` with `item.path`.
    entries = changes_json.get("changeEntries") or changes_json.get("changes") or []
    for c in entries:
        item = c.get("item") or {}
        p = item.get("path")
        if p and isinstance(p, str):
            # remove leading slash
            out.append(p[1:] if p.startswith("/") else p)
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _extract_threads(threads_json: dict) -> List[ExistingDiscussionComment]:
    out: List[ExistingDiscussionComment] = []
    for t in threads_json.get("value", []) or []:
        for c in t.get("comments", []) or []:
            author = ""
            if isinstance(c.get("author"), dict):
                author = c["author"].get("displayName") or c["author"].get("uniqueName") or ""
            out.append(
                ExistingDiscussionComment(
                    author=author,
                    body=c.get("content") or "",
                    url=None,
                    file_path=((t.get("properties") or {}).get("filePath") if isinstance(t.get("properties"), dict) else None),
                    created_at=c.get("publishedDate") or c.get("lastUpdatedDate"),
                    kind="thread",
                )
            )
    return out


def _latest_iteration_id(
    client: httpx.Client,
    *,
    base: str,
    repo: str,
    pr_number: int,
    headers: dict,
    auth,
) -> int:
    url = f"{base}/_apis/git/repositories/{repo}/pullRequests/{pr_number}/iterations?{urlencode({'api-version': '7.1-preview.1'})}"
    data = _get_json(client, url, headers=headers, auth=auth)
    vals = data.get("value") or []
    if not vals:
        return 1
    # pick max numeric id
    ids = []
    for it in vals:
        try:
            ids.append(int(it.get("id")))
        except Exception:
            pass
    return max(ids) if ids else 1


def _get_iteration_changes(
    client: httpx.Client,
    *,
    base: str,
    repo: str,
    pr_number: int,
    iteration_id: int,
    headers: dict,
    auth,
) -> dict:
    # Paginate because large PRs can have many change entries.
    all_entries = []
    skip = 0
    top = 500
    while True:
        params = {"api-version": "7.1-preview.1", "$top": str(top), "$skip": str(skip)}
        url = f"{base}/_apis/git/repositories/{repo}/pullRequests/{pr_number}/iterations/{iteration_id}/changes?{urlencode(params)}"
        data = _get_json(client, url, headers=headers, auth=auth)
        entries = data.get("changeEntries") or []
        all_entries.extend(entries)
        if len(entries) < top:
            break
        skip += top
        if skip > 5000:
            break
    # return unified shape
    return {"changeEntries": all_entries}


def _compute_file_diff(
    client: httpx.Client,
    *,
    base: str,
    repo: str,
    path: str,
    base_commit: str,
    target_commit: str,
    headers: dict,
    auth,
) -> Optional[str]:
    before = _get_item_content(client, base=base, repo=repo, path=path, commit=base_commit, headers=headers, auth=auth)
    after = _get_item_content(client, base=base, repo=repo, path=path, commit=target_commit, headers=headers, auth=auth)
    if before is None and after is None:
        return None
    before_lines = (before or "").splitlines(keepends=True)
    after_lines = (after or "").splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    text = "\n".join(diff) + "\n"
    if len(text) > 200_000:
        return text[:200_000] + "\n... (diff truncated)\n"
    return text


def _get_item_content(
    client: httpx.Client,
    *,
    base: str,
    repo: str,
    path: str,
    commit: str,
    headers: dict,
    auth,
) -> Optional[str]:
    # includeContent=true returns content for text; binary returns metadata
    params = {
        "path": f"/{path}",
        "includeContent": "true",
        "resolveLfs": "true",
        "versionDescriptor.version": commit,
        "versionDescriptor.versionType": "commit",
        "api-version": "7.1-preview.1",
    }
    # repo is already encoded segment
    url = f"{base}/_apis/git/repositories/{repo}/items?{urlencode(params)}"
    r = client.get(url, headers=headers, auth=auth)
    if r.status_code == 404:
        return None
    if r.status_code in {401, 403}:
        raise AuthRequiredError("azure", urlparse(url).netloc, f"Azure DevOps auth failed ({r.status_code}).")
    if r.status_code >= 400:
        raise ProviderError(f"Azure DevOps items error {r.status_code}: {r.text[:500]}")
    # Azure returns raw content (not JSON) when includeContent=true
    # Heuristic: if content looks like JSON with 'content' field, parse it; otherwise treat as plain text.
    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        try:
            j = r.json()
        except json.JSONDecodeError:
            body = (r.text or "")[:800]
            if "text/html" in ct or "<html" in body.lower():
                raise AuthRequiredError(
                    "azure",
                    urlparse(url).netloc,
                    "Azure DevOps returned HTML instead of JSON from items endpoint. PAT may be missing/invalid.",
                )
            raise ProviderError(f"Azure DevOps items returned invalid JSON. Body: {body}")
        if isinstance(j, dict):
            return j.get("content")
        return None
    return r.text


def _get_json(client: httpx.Client, url: str, *, headers: dict, auth) -> dict:
    r = client.get(url, headers=headers, auth=auth)
    if r.status_code in {401, 403}:
        raise AuthRequiredError("azure", urlparse(url).netloc, f"Azure DevOps auth failed ({r.status_code}).")
    if r.status_code >= 400:
        raise ProviderError(f"Azure DevOps API error {r.status_code}: {r.text[:500]}")
    # Azure sometimes returns an HTML login page (200) when auth is missing/invalid
    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        body = (r.text or "")[:800]
        if "text/html" in ct or "<html" in body.lower():
            raise AuthRequiredError(
                "azure",
                urlparse(url).netloc,
                "Azure DevOps returned HTML instead of JSON. Your PAT may be missing/invalid or saved under the wrong host.",
            )
        raise ProviderError(f"Azure DevOps returned non-JSON response (content-type: {ct}). Body: {body}")
    try:
        return r.json()
    except json.JSONDecodeError:
        body = (r.text or "")[:800]
        raise ProviderError(f"Azure DevOps returned invalid JSON. Body: {body}")


def _enc_seg(seg: str) -> str:
    """
    Encode a single URL path segment safely, avoiding double-encoding.
    Accepts raw segments with spaces OR already-encoded segments with %20.
    """
    return quote(unquote(seg or ""), safe="")


