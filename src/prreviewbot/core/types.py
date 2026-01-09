from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChangedFile:
    path: str
    patch: Optional[str] = None  # unified diff for this file (if available)


@dataclass
class ExistingDiscussionComment:
    """
    Existing PR discussion pulled from the provider.
    This is used as context so the LLM can evaluate prior review comments and author justifications.
    """

    author: str
    body: str
    url: Optional[str] = None
    file_path: Optional[str] = None
    created_at: Optional[str] = None
    kind: str = "comment"  # "review_comment" | "issue_comment" | "thread" | "comment"


@dataclass
class PullRequestInfo:
    provider: str
    host: str
    pr_url: str
    title: str
    description: str
    changed_files: List[ChangedFile] = field(default_factory=list)
    existing_discussion: List[ExistingDiscussionComment] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewComment:
    file_path: Optional[str]
    severity: str  # "info" | "warn" | "error"
    message: str
    suggestion: Optional[str] = None
    code_example: Optional[str] = None
    # Best-effort line range in the "new" file after applying the PR changes.
    # If unknown/uncertain, keep as None.
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    line_side: Optional[str] = None  # "new" | "old" | None
    # Optional link to an existing PR discussion comment this suggestion is responding to.
    related_url: Optional[str] = None
    kind: Optional[str] = None  # e.g. "code_suggestion" | "discussion_reply"


@dataclass
class ReviewResult:
    pr_url: str
    language: str
    model: str
    summary: str
    comments: List[ReviewComment] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"## PR Review\n")
        lines.append(f"- **PR**: {self.pr_url}")
        lines.append(f"- **Language**: {self.language}")
        lines.append(f"- **Model**: {self.model}\n")
        lines.append("### Summary\n")
        lines.append(self.summary.strip() + "\n")
        lines.append("### Suggestions\n")
        if not self.comments:
            lines.append("- No suggestions generated.\n")
            return "\n".join(lines)
        for c in self.comments:
            loc = f"`{c.file_path}`: " if c.file_path else ""
            lines.append(f"- **{c.severity.upper()}** {loc}{c.message}")
            if c.suggestion:
                lines.append(f"  - Suggestion: {c.suggestion}")
        lines.append("")
        return "\n".join(lines)


