from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx

from prreviewbot.core.types import PullRequestInfo


@dataclass(frozen=True)
class ProviderContext:
    pr_url: str
    token: Optional[str]
    timeout_s: float = 30.0


class Provider(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fetch_pr(self, ctx: ProviderContext) -> PullRequestInfo: ...

    def post_comment(self, ctx: ProviderContext, *, body_markdown: str) -> str:
        """Post a general (non-inline) comment to the PR/MR. Returns a URL/id string if available."""
        raise NotImplementedError

    def _client(self, ctx: ProviderContext) -> httpx.Client:
        return httpx.Client(timeout=ctx.timeout_s, follow_redirects=True)


