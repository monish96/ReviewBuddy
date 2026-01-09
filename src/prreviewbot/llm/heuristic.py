from __future__ import annotations

import re
from typing import List

from prreviewbot.core.types import ChangedFile, ReviewComment, ReviewResult
from prreviewbot.llm.base import LLM


class HeuristicLLM(LLM):
    """
    Zero-setup fallback reviewer.
    Not as smart as an LLM, but always available and useful for basic hygiene.
    """

    def name(self) -> str:
        return "heuristic"

    def review(self, *, pr_url: str, language: str, files: List[ChangedFile], discussion) -> ReviewResult:
        comments: List[ReviewComment] = []
        total_patch_lines = sum((f.patch or "").count("\n") for f in files)

        summary_bits = []
        summary_bits.append(f"Reviewed {len(files)} changed file(s).")
        if total_patch_lines:
            summary_bits.append(f"Diff size ~{total_patch_lines} line(s).")
        summary_bits.append("Heuristic mode (no external LLM configured).")
        summary = "\n".join([f"- {b}" for b in summary_bits])

        for f in files:
            p = f.patch or ""
            if not p:
                continue
            if re.search(r"password\s*=", p, re.IGNORECASE) or re.search(r"api[_-]?key", p, re.IGNORECASE):
                comments.append(
                    ReviewComment(
                        file_path=f.path,
                        severity="warn",
                        message="Potential secret material detected in diff.",
                        suggestion="Confirm no credentials/tokens are committed; use env vars/secret manager.",
                    )
                )
            if "TODO" in p or "FIXME" in p:
                comments.append(
                    ReviewComment(
                        file_path=f.path,
                        severity="info",
                        message="TODO/FIXME present in changes.",
                        suggestion="Make sure TODOs are tracked or resolved before merge.",
                    )
                )
            if language in {"python"} and ("print(" in p):
                comments.append(
                    ReviewComment(
                        file_path=f.path,
                        severity="info",
                        message="Debug prints added/modified.",
                        suggestion="Consider using structured logging instead of print in production code.",
                    )
                )
            if language in {"javascript", "typescript"} and ("console.log" in p):
                comments.append(
                    ReviewComment(
                        file_path=f.path,
                        severity="info",
                        message="console.log added/modified.",
                        suggestion="Consider a logger or remove before merge.",
                    )
                )

        # global suggestions
        comments.append(
            ReviewComment(
                file_path=None,
                severity="info",
                message="Run formatting + tests before merge.",
                suggestion="Ensure CI passes; add/adjust tests for new behavior and edge cases.",
            )
        )
        if len(files) > 20:
            comments.append(
                ReviewComment(
                    file_path=None,
                    severity="warn",
                    message="Large PR (many changed files).",
                    suggestion="Consider splitting into smaller PRs for easier review/rollback.",
                )
            )

        return ReviewResult(
            pr_url=pr_url,
            language=language,
            model=self.name(),
            summary=summary,
            comments=comments,
        )


