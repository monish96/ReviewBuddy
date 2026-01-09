from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

from prreviewbot.core.types import ChangedFile, ExistingDiscussionComment, ReviewResult


class LLM(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def review(
        self,
        *,
        pr_url: str,
        language: str,
        files: List[ChangedFile],
        discussion: List[ExistingDiscussionComment],
    ) -> ReviewResult: ...


def build_review_prompt(language: str, files: List[ChangedFile], discussion: List[ExistingDiscussionComment] | None = None) -> str:
    chunks: List[Tuple[str, str]] = []
    for f in files:
        if not f.patch:
            continue
        chunks.append((f.path, f.patch))
    discussion = discussion or []
    discussion_block = ""
    if discussion:
        # Keep this short to avoid token blowups.
        items = []
        for d in discussion[:30]:
            loc = f" file={d.file_path}" if d.file_path else ""
            url = f" url={d.url}" if d.url else ""
            body = (d.body or "").strip()
            if len(body) > 800:
                body = body[:800] + "…"
            items.append(f"- [{d.kind}] author={d.author}{loc}{url}\n  {body}")
        discussion_block = "\n\nEXISTING REVIEW DISCUSSION:\n" + "\n".join(items) + "\n"

    if not chunks:
        return (
            f"You are a senior engineer. Review this PR for {language}. "
            "No diffs were available; provide general review guidance and questions to ask."
            + discussion_block
        )

    body = "\n\n".join([f"FILE: {path}\nPATCH:\n{patch}" for path, patch in chunks])
    return (
        f"You are a senior engineer doing a careful PR review for {language}.\n"
        "Return a concise review with:\n"
        "1) Summary (3-6 bullets)\n"
        "2) Issues (with severity: info|warn|error)\n"
        "3) Concrete suggestions (prefer actionable edits)\n"
        "4) If there are existing review comments and author justifications, evaluate them. "
        "If you disagree with the justification, propose a respectful reply suggestion.\n"
        "When a suggestion benefits from code, include a short code example (fenced) the dev can paste.\n"
        "Be pragmatic and avoid nitpicking.\n\n"
        f"{body}"
        f"{discussion_block}"
    )


