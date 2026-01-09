from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    entry = root / "src" / "prreviewbot" / "__main__.py"
    if not entry.exists():
        print(f"Entry not found: {entry}", file=sys.stderr)
        return 2

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "prreviewbot",
        "--add-data",
        f"{root / 'src' / 'prreviewbot' / 'web' / 'templates'}:prreviewbot/web/templates",
        "--add-data",
        f"{root / 'src' / 'prreviewbot' / 'web' / 'static'}:prreviewbot/web/static",
        str(entry),
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(root))
    print("\nBuilt. Run: ./dist/prreviewbot serve\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


