from __future__ import annotations

from typing import Optional


def format_pr_comment_markdown(
    *,
    pr_link: str,
    file_path: Optional[str],
    severity: Optional[str],
    message: str,
    suggestion: Optional[str],
    code_example: Optional[str],
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    related_url: Optional[str] = None,
) -> str:
    sev = (severity or "info").strip().lower()
    header = f"**{sev.upper()}**"
    if file_path:
        header += f" in `{file_path}`"
    if start_line and end_line:
        if end_line < start_line:
            start_line, end_line = end_line, start_line
        header += f" (L{start_line}–L{end_line})"

    parts = [header, "", message.strip()]
    if related_url:
        parts += ["", f"**Context**: {related_url}"]
    if suggestion:
        parts += ["", "**Suggestion**", suggestion.strip()]

    if code_example:
        ce = code_example.strip()
        if not ce.startswith("```"):
            ce = "```" + "\n" + ce + "\n```"
        parts += ["", "**Code example**", ce]

    parts += ["", f"_Posted via PRreviewBot_"]
    return "\n".join([p for p in parts if p is not None])


