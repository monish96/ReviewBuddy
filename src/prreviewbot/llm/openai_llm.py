from __future__ import annotations

import json
import re
from typing import List, Optional

from prreviewbot.core.errors import PRReviewBotError
from prreviewbot.core.types import ChangedFile, ReviewComment, ReviewResult
from prreviewbot.llm.base import LLM, build_review_prompt


class OpenAILLM(LLM):
    def __init__(self, *, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    def name(self) -> str:
        return f"openai:{self._model}"

    def review(self, *, pr_url: str, language: str, files: List[ChangedFile], discussion) -> ReviewResult:
        # Optional dependency
        try:
            from openai import OpenAI  # type: ignore
        except ModuleNotFoundError as e:
            raise PRReviewBotError(
                "OpenAI support is not installed. Install with: pip install -e '.[openai]'"
            ) from e

        client = OpenAI(api_key=self._api_key)
        prompt = build_review_prompt(language, files, discussion=discussion or [])

        system = (
            "You are a PR review assistant. "
            "Output MUST be JSON with keys: summary (string), comments (array). "
            "Each comment: {file_path|null, severity: info|warn|error, message, suggestion|null, code_example|null, start_line|null, end_line|null, line_side|null, related_url|null, kind|null}.\n"
            "For line numbers: use NEW file line numbers derived from the diff hunks (@@ -a,b +c,d @@). If unsure, set them to null."
            "If responding to an existing review comment thread, set kind='discussion_reply' and include related_url pointing to that thread/comment."
        )
        resp = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
        parsed = _safe_json(content)
        if not parsed:
            # fallback: treat as plain summary
            return ReviewResult(
                pr_url=pr_url,
                language=language,
                model=self.name(),
                summary=content.strip() or "No content returned by model.",
                comments=[],
            )

        summary_val = parsed.get("summary")
        if isinstance(summary_val, list):
            summary_text = "\n".join([f"- {str(x).strip()}" for x in summary_val if str(x).strip()])
        else:
            summary_text = str(summary_val or "").strip()

        comments: List[ReviewComment] = []
        for c in parsed.get("comments", []) or []:
            comments.append(
                ReviewComment(
                    file_path=c.get("file_path"),
                    severity=(c.get("severity") or "info").lower(),
                    message=str(c.get("message") or "").strip(),
                    suggestion=(str(c.get("suggestion")).strip() if c.get("suggestion") else None),
                    code_example=(str(c.get("code_example")).strip() if c.get("code_example") else None),
                    start_line=(int(c["start_line"]) if isinstance(c.get("start_line"), (int, float, str)) and str(c.get("start_line")).strip().isdigit() else None),
                    end_line=(int(c["end_line"]) if isinstance(c.get("end_line"), (int, float, str)) and str(c.get("end_line")).strip().isdigit() else None),
                    line_side=(str(c.get("line_side")).strip().lower() if c.get("line_side") else None),
                    related_url=(str(c.get("related_url")).strip() if c.get("related_url") else None),
                    kind=(str(c.get("kind")).strip().lower() if c.get("kind") else None),
                )
            )

        return ReviewResult(
            pr_url=pr_url,
            language=language,
            model=self.name(),
            summary=summary_text or "No summary.",
            comments=comments,
        )


def _safe_json(s: str) -> Optional[dict]:
    s = s.strip()
    # common: model wraps json in ```json ... ```
    if s.startswith("```"):
        # strip the first and last fence, keep inner content
        parts = s.split("```")
        if len(parts) >= 3:
            s = parts[1]
        else:
            s = s.strip("`")
    s = s.strip()
    # Remove optional language tag prefix like "json\n"
    s = re.sub(r"^\s*json\s*\n", "", s, flags=re.IGNORECASE)
    try:
        return json.loads(s)
    except Exception:
        return None


