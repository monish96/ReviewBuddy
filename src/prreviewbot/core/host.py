from __future__ import annotations

from urllib.parse import urlparse


def normalize_host(value: str) -> str:
    """
    Normalize a user-provided host value to a bare lowercase netloc.

    Examples:
    - "https://dev.azure.com" -> "dev.azure.com"
    - "dev.azure.com/foo" -> "dev.azure.com"
    - "GITHUB.COM" -> "github.com"
    """
    v = (value or "").strip()
    if not v:
        return ""
    if "://" in v:
        u = urlparse(v)
        v = u.netloc or ""
    if "/" in v:
        v = v.split("/", 1)[0]
    return v.lower()


