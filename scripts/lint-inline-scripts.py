#!/usr/bin/env python3
"""Guardrail against `//` line comments inside inline <script> blocks.

Jekyll's `compress_html` filter strips newlines from <script> tag bodies in
production builds. That turns every `//` line comment into one that runs to
the end of the script tag - silently swallowing any code that follows.

Use `/* ... */` block comments instead. This script enforces that rule across
every Liquid include / layout / page in the project so the bug cannot ship
again.

Usage:
    python scripts/lint-inline-scripts.py [path ...]

Exits 0 when clean, 1 when violations are found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Default scan paths. The directories most likely to host inline scripts.
DEFAULT_TARGETS = ["_includes", "_layouts", "_tabs"]

# Capture only inline scripts - skip those with `src=...` and JSON-LD blocks.
SCRIPT_BLOCK_RE = re.compile(
    r"<script(?P<attrs>(?:\s+[^>]*)?)>(?P<body>.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)
SRC_ATTR_RE = re.compile(r"\bsrc\s*=", re.IGNORECASE)
JSON_LD_RE = re.compile(r"type\s*=\s*[\"']application/ld\+json[\"']", re.IGNORECASE)

# A pure comment line: optional whitespace, then `//`, not part of a URL or `///` regex.
LINE_COMMENT_RE = re.compile(r"^\s*//(?!/)")


def offset_to_line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return a list of (line_number, snippet) for offending // comments."""
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[tuple[int, str]] = []
    for block in SCRIPT_BLOCK_RE.finditer(source):
        attrs = block.group("attrs") or ""
        if SRC_ATTR_RE.search(attrs) or JSON_LD_RE.search(attrs):
            continue

        body = block.group("body")
        body_start = block.start("body")
        for line_offset, raw_line in enumerate(body.split("\n")):
            if not LINE_COMMENT_RE.match(raw_line):
                continue
            absolute_line = offset_to_line(source, body_start) + line_offset
            findings.append((absolute_line, raw_line.strip()))
    return findings


def iter_html_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_file() and target.suffix in {".html", ".htm"}:
            files.append(target)
        elif target.is_dir():
            files.extend(sorted(target.rglob("*.html")))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to scan (default: _includes _layouts _tabs).",
    )
    args = parser.parse_args()

    if args.paths:
        targets = [Path(p).resolve() for p in args.paths]
    else:
        targets = [REPO_ROOT / d for d in DEFAULT_TARGETS]
        targets = [t for t in targets if t.exists()]

    files = iter_html_files(targets)
    if not files:
        print("No HTML files found in scan paths.", file=sys.stderr)
        return 0

    total_violations = 0
    for path in files:
        findings = scan_file(path)
        if not findings:
            continue
        rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        for line_no, snippet in findings:
            print(f"{rel}:{line_no}: inline script uses '//' line comment -> {snippet}")
            total_violations += 1

    if total_violations:
        print()
        print(
            f"Found {total_violations} `//` line comment(s) inside inline <script> blocks.",
            file=sys.stderr,
        )
        print(
            "Convert each to a /* ... */ block comment so jekyll's `compress_html` "
            "(production-only) does not collapse the surrounding newline and let the "
            "comment swallow following statements.",
            file=sys.stderr,
        )
        return 1

    print(f"OK - {len(files)} file(s) scanned, no inline `//` comments inside <script>.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
