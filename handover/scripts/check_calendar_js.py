#!/usr/bin/env python3
"""Refuse to publish dorm-calendar index.html if bedmap-js or i18n-js is invalid JS.

Usage: python3 check_calendar_js.py path/to/index.html
Exit 0 = ok; exit 1 = SyntaxError / missing script (do not push).
"""
import re, subprocess, sys, tempfile
from pathlib import Path

def check(html_path: str) -> None:
    h = Path(html_path).read_text(encoding="utf-8")
    for sid in ("bedmap-js", "i18n-js"):
        m = re.search(rf'<script id="{sid}">(.*?)</script>', h, re.S)
        if not m:
            raise SystemExit(f'missing <script id="{sid}"> in {html_path}')
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(m.group(1))
            path = f.name
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        Path(path).unlink(missing_ok=True)
        if r.returncode != 0:
            raise SystemExit(f"{sid} SyntaxError — do not push:\n{r.stderr}")
        print(sid, "ok")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_calendar_js.py index.html")
    check(sys.argv[1])
