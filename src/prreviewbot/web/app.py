from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from prreviewbot.core.errors import AuthRequiredError, PRReviewBotError, ProviderError
from prreviewbot.core.host import normalize_host
from prreviewbot.core.link_parser import parse_pr_link
from prreviewbot.core.review_service import ReviewService
from prreviewbot.storage.config import AppConfig, ConfigStore
from prreviewbot.web.branding import app_name, app_tagline


class ReviewRequest(BaseModel):
    pr_link: str = Field(..., description="PR URL")
    language: Optional[str] = Field(None, description="Language override, or null for auto")
    llm_provider: Optional[str] = Field(None, description="Override LLM provider for this request")
    llm_model: Optional[str] = Field(None, description="Override model/deployment for this request")


class SettingsUpsert(BaseModel):
    # auth: store token for provider+host
    provider: str
    host: str
    token: str


class SettingsDelete(BaseModel):
    provider: str
    host: str


class LLMSettings(BaseModel):
    provider: str = "heuristic"  # heuristic|openai
    default_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    # Generic custom endpoint fields (AzureOpenAI-compatible gateways)
    openai_endpoint: Optional[str] = None
    openai_api_version: Optional[str] = None
    openai_deployment: Optional[str] = None
    # Backward compatibility (older UI keys)
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    azure_openai_api_key: Optional[str] = None


class PostCommentRequest(BaseModel):
    pr_link: str
    file_path: Optional[str] = None
    severity: Optional[str] = None
    message: str
    suggestion: Optional[str] = None
    code_example: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    related_url: Optional[str] = None


def create_app(*, data_dir: Optional[Path] = None) -> FastAPI:
    # When deployed behind a reverse proxy under a path prefix (e.g. /pr-review),
    # set PRREVIEWBOT_ROOT_PATH=/pr-review so url_for() generates correct links.
    root_path = (os.getenv("PRREVIEWBOT_ROOT_PATH") or "").rstrip("/")
    app = FastAPI(title=app_name(), version="0.1.0", root_path=root_path)

    templates_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    templates = Jinja2Templates(directory=str(templates_dir))
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    store = ConfigStore(data_dir=data_dir)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/favicon.ico")
    def favicon(request: Request):
        # avoid 404 spam; browsers will accept SVG too
        return RedirectResponse(url=str(request.url_for("static", path="icon.svg")))

    @app.get("/", response_class=HTMLResponse)
    def landing(request: Request):
        return templates.TemplateResponse(
            request,
            "landing.html",
            {
                "request": request,
                "tool_path": str(request.url_for("tool")),
                "app_name": app_name(),
                "app_tagline": app_tagline(),
            },
        )

    @app.get("/index.html", response_class=HTMLResponse)
    def index_html(request: Request):
        # Gateway compatibility: serve the same page as "/"
        return templates.TemplateResponse(
            request,
            "landing.html",
            {
                "request": request,
                "tool_path": str(request.url_for("tool")),
                "app_name": app_name(),
                "app_tagline": app_tagline(),
            },
        )

    @app.get("/tool", response_class=HTMLResponse)
    def tool(request: Request):
        return templates.TemplateResponse(request, "tool.html", {"request": request, "app_name": app_name()})

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request):
        cfg = store.load()
        return templates.TemplateResponse(
            request,
            "settings.html",
            {"request": request, "settings": _safe_settings(cfg), "app_name": app_name()},
        )

    @app.get("/api/settings")
    def get_settings():
        return _safe_settings(store.load())

    @app.post("/api/settings/token")
    def upsert_token(payload: SettingsUpsert):
        cfg = store.load()
        provider = (payload.provider or "").strip().lower()
        host = normalize_host(payload.host)
        cfg.tokens.setdefault(provider, {})
        cfg.tokens[provider][host] = payload.token
        store.save(cfg)
        return {"ok": True, "host": host}

    @app.post("/api/settings/token/delete")
    def delete_token(payload: SettingsDelete):
        cfg = store.load()
        provider = (payload.provider or "").strip().lower()
        host = normalize_host(payload.host)
        if provider in (cfg.tokens or {}) and host in (cfg.tokens.get(provider) or {}):
            del cfg.tokens[provider][host]
            if not cfg.tokens[provider]:
                del cfg.tokens[provider]
            store.save(cfg)
        return {"ok": True, "host": host}

    @app.post("/api/settings/llm")
    def set_llm(payload: LLMSettings):
        cfg = store.load()
        cfg.llm = {
            "provider": payload.provider,
            "default_model": payload.default_model,
            "openai_api_key": payload.openai_api_key,
            "openai_endpoint": payload.openai_endpoint or payload.azure_openai_endpoint,
            "openai_api_version": payload.openai_api_version or payload.azure_openai_api_version,
            "openai_deployment": payload.openai_deployment or payload.azure_openai_deployment,
            # keep old key read-compatible, but we store the canonical name
        }
        store.save(cfg)
        return {"ok": True}

    @app.post("/api/settings/llm/clear")
    def clear_llm():
        cfg = store.load()
        cfg.llm = {}
        store.save(cfg)
        return {"ok": True}

    @app.post("/api/review")
    def review(payload: ReviewRequest, request: Request):
        cfg = store.load()
        service = ReviewService.from_config(cfg)
        try:
            result = service.review(
                pr_link=payload.pr_link,
                language=payload.language,
                llm_provider=payload.llm_provider,
                llm_model=payload.llm_model,
            )
            parsed = parse_pr_link(payload.pr_link)
            return JSONResponse(
                {
                    "pr_url": result.pr_url,
                    "provider": parsed.provider,
                    "host": parsed.host,
                    "language": result.language,
                    "model": result.model,
                    "summary": result.summary,
                    "comments": [
                        {
                            "file_path": c.file_path,
                            "severity": c.severity,
                            "message": c.message,
                            "suggestion": c.suggestion,
                            "code_example": c.code_example,
                            "start_line": c.start_line,
                            "end_line": c.end_line,
                            "line_side": c.line_side,
                            "related_url": c.related_url,
                            "kind": c.kind,
                        }
                        for c in result.comments
                    ],
                }
            )
        except AuthRequiredError as e:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": str(e),
                    "provider": e.provider,
                    "host": e.host,
                    "settings_url": str(request.url_for("settings_page")),
                },
            )
        except PRReviewBotError as e:
            raise HTTPException(status_code=400, detail={"error": str(e)})
        except Exception as e:
            raise HTTPException(status_code=500, detail={"error": f"Unexpected error: {e}"})

    @app.post("/api/pr/comment")
    def post_comment(payload: PostCommentRequest, request: Request):
        cfg = store.load()
        service = ReviewService.from_config(cfg)
        try:
            url = service.post_comment(
                pr_link=payload.pr_link,
                file_path=payload.file_path,
                severity=payload.severity,
                message=payload.message,
                suggestion=payload.suggestion,
                code_example=payload.code_example,
                start_line=payload.start_line,
                end_line=payload.end_line,
                related_url=payload.related_url,
            )
            return {"ok": True, "comment_url": url}
        except AuthRequiredError as e:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": str(e),
                    "provider": e.provider,
                    "host": e.host,
                    "settings_url": str(request.url_for("settings_page")),
                },
            )
        except (PRReviewBotError, ProviderError) as e:
            raise HTTPException(status_code=400, detail={"error": str(e)})
        except Exception as e:
            raise HTTPException(status_code=500, detail={"error": f"Unexpected error: {e}"})

    return app


def _safe_settings(cfg: AppConfig) -> Dict[str, Any]:
    def mask(tok: str) -> str:
        if not tok:
            return ""
        if len(tok) <= 8:
            return "*" * len(tok)
        return "*" * (len(tok) - 4) + tok[-4:]

    tokens = {}
    for provider, hosts in (cfg.tokens or {}).items():
        tokens[provider] = {h: mask(t) for h, t in (hosts or {}).items()}

    return {
        "tokens": tokens,
        "llm": {
            "provider": (cfg.llm or {}).get("provider") or "heuristic",
            "default_model": (cfg.llm or {}).get("default_model") or "",
            "openai_api_key": mask((cfg.llm or {}).get("openai_api_key") or ""),
            "openai_endpoint": (cfg.llm or {}).get("openai_endpoint") or "",
            "openai_api_version": (cfg.llm or {}).get("openai_api_version") or "",
            "openai_deployment": (cfg.llm or {}).get("openai_deployment") or "",
        },
        "model_map": cfg.model_map or {},
    }


