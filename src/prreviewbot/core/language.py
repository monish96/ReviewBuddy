from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional

from prreviewbot.core.types import ChangedFile


EXT_TO_LANG = {
    ".py": "python",
    ".ipynb": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".scala": "scala",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".tf": "terraform",
    ".md": "markdown",
}


def detect_language(changed_files: Iterable[ChangedFile], override: Optional[str] = None) -> str:
    if override:
        return normalize_language(override)
    counts = Counter()
    for f in changed_files:
        ext = "." + f.path.split(".")[-1].lower() if "." in f.path else ""
        lang = EXT_TO_LANG.get(ext)
        if lang:
            counts[lang] += 1
    if counts:
        return counts.most_common(1)[0][0]
    return "general"


def normalize_language(lang: str) -> str:
    return lang.strip().lower().replace(" ", "").replace("-", "")


