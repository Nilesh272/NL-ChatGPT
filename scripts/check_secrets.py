#!/usr/bin/env python3
"""Scan tracked project files for likely API key leaks (Phase 6 security pass)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Patterns that often indicate committed secrets
PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "OpenAI-style key (sk-...)"),
    (re.compile(r"gsk_[a-zA-Z0-9]{20,}"), "Groq key (gsk_...)"),
    (re.compile(r"tvly-[a-zA-Z0-9]{20,}"), "Tavily key (tvly-...)"),
    (re.compile(r"pplx-[a-zA-Z0-9]{20,}"), "Perplexity key (pplx-...)"),
]

SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", "eval/results"}
SKIP_FILES = {".env", ".env.local", ".env.production"}
ALLOWED_PREFIXES = ("OPENAI_API_KEY=", "GROQ_API_KEY=", "TAVILY_API_KEY=", "PERPLEXITY_API_KEY=")


def _git_tracked_files() -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "ls-files"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in ROOT.rglob("*") if p.is_file() and not any(s in p.parts for s in SKIP_DIRS)]

    paths = []
    for line in out.strip().splitlines():
        p = ROOT / line
        if p.is_file():
            paths.append(p)
    return paths


def _should_scan(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return False
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    if path.suffix in {".pyc", ".png", ".jpg", ".gif", ".pdf", ".db", ".sqlite"}:
        return False
    return True


def scan() -> list[tuple[str, int, str, str]]:
    findings: list[tuple[str, int, str, str]] = []
    for path in _git_tracked_files():
        if not _should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(ROOT))
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if any(stripped.startswith(prefix) for prefix in ALLOWED_PREFIXES):
                if "your_" in stripped.lower() or "..." in stripped or "xxx" in stripped.lower():
                    continue
            for pattern, label in PATTERNS:
                if pattern.search(line):
                    findings.append((rel, lineno, label, line.strip()[:80]))
    return findings


def main() -> int:
    findings = scan()
    if not findings:
        print("check-secrets: OK — no likely API keys in tracked files.")
        return 0
    print("check-secrets: FAILED — possible secrets found:")
    for rel, lineno, label, snippet in findings:
        print(f"  {rel}:{lineno} [{label}] {snippet}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
