from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class UnifiedDiffHunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int

    @property
    def new_range(self) -> Tuple[int, int]:
        start = self.new_start
        end = self.new_start + max(self.new_len, 0) - 1
        if self.new_len == 0:
            end = start
        return start, end


_HUNK_RE = re.compile(r"^@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@")


def parse_unified_diff_hunks(patch: str) -> List[UnifiedDiffHunk]:
    hunks: List[UnifiedDiffHunk] = []
    for line in (patch or "").splitlines():
        m = _HUNK_RE.match(line)
        if not m:
            continue
        old_start = int(m.group(1))
        old_len = int(m.group(2) or "1")
        new_start = int(m.group(3))
        new_len = int(m.group(4) or "1")
        hunks.append(UnifiedDiffHunk(old_start=old_start, old_len=old_len, new_start=new_start, new_len=new_len))
    return hunks


def validate_line_range_against_patch(
    *,
    patch: Optional[str],
    start_line: Optional[int],
    end_line: Optional[int],
    side: Optional[str],
) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Ensure (start_line, end_line) falls within a diff hunk range so we don't display hallucinated line numbers.
    Only validates against "new" ranges (default) unless side=="old".
    """
    if not patch or not start_line or not end_line:
        return None, None, None
    if start_line < 1 or end_line < 1:
        return None, None, None
    if end_line < start_line:
        start_line, end_line = end_line, start_line

    hunks = parse_unified_diff_hunks(patch)
    if not hunks:
        return None, None, None

    s = (side or "new").lower()
    if s not in {"new", "old"}:
        s = "new"

    for h in hunks:
        if s == "new":
            hs, he = h.new_range
        else:
            hs = h.old_start
            he = h.old_start + max(h.old_len, 0) - 1
            if h.old_len == 0:
                he = hs
        if start_line >= hs and end_line <= he:
            return start_line, end_line, s

    return None, None, None


