#!/usr/bin/env bash
# Move a draft from _drafts/<slug>.md to _posts/YYYY-MM-DD-<slug>.md.
# Stamps a `date:` line into the front matter if missing.
#
# Usage:
#   scripts/publish-post.sh <slug>

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRAFTS="$ROOT/_drafts"
POSTS="$ROOT/_posts"

if [ $# -lt 1 ]; then
  echo "usage: $0 <slug>" >&2
  exit 1
fi

SLUG="$1"
SRC="$DRAFTS/$SLUG.md"
if [ ! -f "$SRC" ]; then
  echo "error: $SRC not found" >&2
  exit 1
fi

TODAY=$(date +%Y-%m-%d)
NOW=$(date +"%Y-%m-%d %H:%M:%S %z")
DST="$POSTS/$TODAY-$SLUG.md"

if [ -e "$DST" ]; then
  echo "error: $DST already exists" >&2
  exit 1
fi

if grep -q '^date:' "$SRC"; then
  cp "$SRC" "$DST"
else
  awk -v d="$NOW" '
    BEGIN { in_fm = 0; done = 0; fm_count = 0 }
    /^---[[:space:]]*$/ {
      fm_count++
      if (fm_count == 1) { in_fm = 1; print; next }
      if (fm_count == 2 && in_fm && !done) {
        print "date: " d
        done = 1
        in_fm = 0
        print
        next
      }
    }
    { print }
  ' "$SRC" > "$DST"
fi

rm "$SRC"

echo "moved $SRC -> $DST"
echo "review, then: git add $DST && git commit"
