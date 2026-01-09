from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class ParsedLink:
    provider: str  # github|gitlab|bitbucket|azure
    host: str
    owner: Optional[str] = None
    repo: Optional[str] = None
    pr_number: Optional[int] = None
    workspace: Optional[str] = None  # bitbucket cloud
    project: Optional[str] = None  # azure
    org: Optional[str] = None  # azure
    namespace_path: Optional[str] = None  # gitlab group/subgroup/project path


def parse_pr_link(pr_url: str) -> ParsedLink:
    u = urlparse(pr_url)
    if not u.scheme or not u.netloc:
        raise ValueError("Invalid URL")
    host = u.netloc
    path = (u.path or "").rstrip("/")

    # GitHub: /{owner}/{repo}/pull/{number}
    m = re.match(r"^/([^/]+)/([^/]+)/pull/(\d+)$", path)
    if m:
        return ParsedLink(
            provider="github",
            host=host,
            owner=m.group(1),
            repo=m.group(2),
            pr_number=int(m.group(3)),
        )

    # Gitea: /{owner}/{repo}/pulls/{number}
    m = re.match(r"^/([^/]+)/([^/]+)/pulls/(\d+)$", path)
    if m:
        return ParsedLink(
            provider="gitea",
            host=host,
            owner=m.group(1),
            repo=m.group(2),
            pr_number=int(m.group(3)),
        )

    # GitLab: /{namespace}/{project}/-/merge_requests/{iid}
    m = re.match(r"^/(.+)/-/merge_requests/(\d+)$", path)
    if m:
        namespace_path = m.group(1)
        return ParsedLink(provider="gitlab", host=host, namespace_path=namespace_path, pr_number=int(m.group(2)))

    # Bitbucket Cloud: /{workspace}/{repo}/pull-requests/{id}
    m = re.match(r"^/([^/]+)/([^/]+)/pull-requests/(\d+)$", path)
    if m and host.endswith("bitbucket.org"):
        return ParsedLink(
            provider="bitbucket",
            host=host,
            workspace=m.group(1),
            repo=m.group(2),
            pr_number=int(m.group(3)),
        )

    # Azure DevOps:
    # https://dev.azure.com/{org}/{project}/_git/{repo}/pullrequest/{id}
    m = re.match(r"^/([^/]+)/([^/]+)/_git/([^/]+)/pullrequest/(\d+)$", path)
    if m and host.endswith("dev.azure.com"):
        return ParsedLink(
            provider="azure",
            host=host,
            org=m.group(1),
            project=m.group(2),
            repo=m.group(3),
            pr_number=int(m.group(4)),
        )

    # Azure legacy: https://{org}.visualstudio.com/{project}/_git/{repo}/pullrequest/{id}
    m = re.match(r"^/([^/]+)/_git/([^/]+)/pullrequest/(\d+)$", path)
    if m and host.endswith("visualstudio.com"):
        org = host.split(".")[0]
        return ParsedLink(
            provider="azure",
            host=host,
            org=org,
            project=m.group(1),
            repo=m.group(2),
            pr_number=int(m.group(3)),
        )

    raise ValueError("Unsupported PR URL format (supported: GitHub, GitLab, Bitbucket Cloud, Azure DevOps).")


