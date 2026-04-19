#!/usr/bin/env bash
# Create a new draft at _drafts/<slug>.md with standard front matter.
#
# Usage:
#   scripts/new-post.sh "Post Title"            # slug auto-derived from title
#   scripts/new-post.sh "Post Title" my-slug    # explicit slug override
#
# Slug rules: lowercase, ASCII, spaces -> dashes, non-[a-z0-9-] stripped.
# If the title is non-ASCII (e.g. Chinese), you MUST pass an explicit slug.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRAFTS="$ROOT/_drafts"

if [ $# -lt 1 ]; then
  echo "usage: $0 \"Post Title\" [slug]" >&2
  exit 1
fi

TITLE="$1"
SLUG="${2:-}"

if [ -z "$SLUG" ]; then
  SLUG=$(printf '%s' "$TITLE" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')
fi

if [ -z "$SLUG" ]; then
  echo "error: could not derive slug from title; pass one explicitly." >&2
  echo "       $0 \"$TITLE\" my-slug" >&2
  exit 1
fi

FILE="$DRAFTS/$SLUG.md"
if [ -e "$FILE" ]; then
  echo "error: $FILE already exists" >&2
  exit 1
fi

mkdir -p "$DRAFTS"

cat > "$FILE" <<EOF
---
title: $TITLE
description:
categories:
tags:
---

EOF

echo "created $FILE"
echo "serve drafts with:  make serve-drafts"
echo "publish with:       make publish slug=$SLUG"
