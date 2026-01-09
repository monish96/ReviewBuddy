from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from prreviewbot.core.language import detect_language
from prreviewbot.core.link_parser import parse_pr_link
from prreviewbot.core.model_select import choose_model
from prreviewbot.core.types import PullRequestInfo, ReviewResult
from prreviewbot.llm.heuristic import HeuristicLLM
import os

from prreviewbot.storage.config import AppConfig
from prreviewbot.core.errors import PRReviewBotError
from prreviewbot.core.comment_format import format_pr_comment_markdown
from prreviewbot.core.diff_hunks import validate_line_range_against_patch


@dataclass
class ReviewService:
    cfg: AppConfig

    @staticmethod
    def from_config(cfg: AppConfig) -> "ReviewService":
        return ReviewService(cfg=cfg)

    def _get_token(self, provider: str, host: str) -> Optional[str]:
        return (self.cfg.tokens.get(provider, {}) or {}).get(host)

    def _build_llm(self, provider: str, model: str, *, strict: bool = False):
        if provider == "openai":
            llm_cfg = self.cfg.llm or {}
            # If openai_endpoint is set, we treat it as an AzureOpenAI-compatible gateway (api-key header).
            endpoint = (
                llm_cfg.get("openai_endpoint")
                or llm_cfg.get("azure_openai_endpoint")  # backward compat
                or os.environ.get("OPENAI_ENDPOINT")
                or os.environ.get("AZURE_OPENAI_ENDPOINT")
                or ""
            )
            api_key = (
                llm_cfg.get("openai_api_key")
                or llm_cfg.get("api_key")
                or llm_cfg.get("azure_openai_api_key")  # backward compat
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("AZURE_OPENAI_API_KEY")
            )

            # Optional dependency
            try:
                import openai  # noqa: F401
            except Exception as e:
                if strict:
                    raise PRReviewBotError(
                        "OpenAI selected but the OpenAI dependency is not installed. Install with: pip install -e '.[openai]'"
                    ) from e
                return HeuristicLLM()

            if not api_key:
                if strict:
                    raise PRReviewBotError(
                        "OpenAI selected but no API key is configured. Add openai_api_key in Settings or set OPENAI_API_KEY."
                    )
                return HeuristicLLM()

            if endpoint:
                api_version = (
                    llm_cfg.get("openai_api_version")
                    or llm_cfg.get("azure_openai_api_version")  # backward compat
                    or os.environ.get("OPENAI_API_VERSION")
                    or os.environ.get("AZURE_OPENAI_API_VERSION")
                    or "2024-02-15-preview"
                )
                # Deployment defaults to the chosen model (or Settings default model)
                deployment = (
                    llm_cfg.get("openai_deployment")
                    or llm_cfg.get("azure_openai_deployment")  # backward compat
                    or model
                    or os.environ.get("OPENAI_DEPLOYMENT")
                    or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
                    or ""
                )
                try:
                    from prreviewbot.llm.azure_openai_llm import AzureOpenAILLM

                    return AzureOpenAILLM(
                        endpoint=str(endpoint).strip(),
                        api_key=str(api_key).strip(),
                        api_version=str(api_version).strip(),
                        deployment=str(deployment).strip() or "default",
                    )
                except Exception as e:
                    if strict:
                        raise PRReviewBotError(f"OpenAI (custom endpoint) failed to initialize: {e}") from e
                    return HeuristicLLM()

            try:
                from prreviewbot.llm.openai_llm import OpenAILLM

                return OpenAILLM(api_key=str(api_key).strip(), model=model)
            except Exception as e:
                if strict:
                    raise PRReviewBotError(f"OpenAI selected but failed to initialize: {e}") from e
                return HeuristicLLM()
        return HeuristicLLM()

    def fetch_pr(self, pr_link: str) -> PullRequestInfo:
        parsed = parse_pr_link(pr_link)
        from prreviewbot.providers.registry import provider_for
        from prreviewbot.providers.base import ProviderContext

        token = self._get_token(parsed.provider, parsed.host)
        provider = provider_for(parsed)
        return provider.fetch_pr(ProviderContext(pr_url=pr_link, token=token))

    def post_comment(
        self,
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
        parsed = parse_pr_link(pr_link)
        from prreviewbot.providers.registry import provider_for
        from prreviewbot.providers.base import ProviderContext

        token = self._get_token(parsed.provider, parsed.host)
        provider = provider_for(parsed)
        body = format_pr_comment_markdown(
            pr_link=pr_link,
            file_path=file_path,
            severity=severity,
            message=message,
            suggestion=suggestion,
            code_example=code_example,
            start_line=start_line,
            end_line=end_line,
            related_url=related_url,
        )
        return provider.post_comment(ProviderContext(pr_url=pr_link, token=token), body_markdown=body)

    def review(
        self,
        *,
        pr_link: str,
        language: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> ReviewResult:
        pr = self.fetch_pr(pr_link)
        detected = detect_language(pr.changed_files, override=language)

        cfg_provider = ((self.cfg.llm or {}).get("provider") or "heuristic").lower()
        cfg_default_model = (self.cfg.llm or {}).get("default_model") or (self.cfg.llm or {}).get("model")
        req_provider = (llm_provider or "").strip().lower() or None
        req_model = (llm_model or "").strip() or None
        effective_provider = req_provider or cfg_provider
        effective_default_model = req_model or cfg_default_model

        choice = choose_model(
            language=detected,
            llm_provider=effective_provider,
            llm_default_model=effective_default_model,
            overrides=self.cfg.model_map or {},
        )
        strict = req_provider is not None or req_model is not None
        llm = self._build_llm(choice.provider, choice.model, strict=strict)
        result = llm.review(pr_url=pr.pr_url, language=detected, files=pr.changed_files, discussion=pr.existing_discussion)

        # Sanitize model-provided line numbers against actual diff hunks.
        patch_by_path = {f.path: f.patch for f in pr.changed_files}
        for c in result.comments:
            if not c.file_path:
                c.start_line, c.end_line, c.line_side = None, None, None
                continue
            start, end, side = validate_line_range_against_patch(
                patch=patch_by_path.get(c.file_path),
                start_line=c.start_line,
                end_line=c.end_line,
                side=c.line_side,
            )
            c.start_line, c.end_line, c.line_side = start, end, side

        return result


