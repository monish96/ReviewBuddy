from __future__ import annotations

import os


def app_name() -> str:
    return os.environ.get("APP_NAME", "Review Buddy").strip() or "Review Buddy"


def app_tagline() -> str:
    return (
        os.environ.get(
            "APP_TAGLINE",
            "AI-powered PR reviews & one-click suggestions across Git platforms",
        ).strip()
        or "AI-powered PR reviews & one-click suggestions across Git platforms"
    )


