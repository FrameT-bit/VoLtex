#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT_DIR="$(dirname "$APP_DIR")"
APP_BASENAME="$(basename "$APP_DIR")"
STAMP="$(date '+%Y%m%d-%H%M%S')"
TARGET="${1:-$PARENT_DIR/$APP_BASENAME-working-$STAMP.zip}"

cd "$PARENT_DIR"
zip -r "$TARGET" "$APP_BASENAME" \
  -x "$APP_BASENAME/.git/*" \
  -x "$APP_BASENAME/.venv/*" \
  -x "$APP_BASENAME/.pytest_cache/*" \
  -x '*/__pycache__/*' \
  -x '*.pyc' \
  -x '*.zip'

unzip -t "$TARGET" >/dev/null
printf '%s\n' "$TARGET"
