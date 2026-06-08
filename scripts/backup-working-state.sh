#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT_DIR="$(dirname "$APP_DIR")"
STAMP="$(date '+%Y%m%d-%H%M%S')"
TARGET="$PARENT_DIR/voltex-working-$STAMP.zip"

cd "$PARENT_DIR"
zip -r "$TARGET" "$(basename "$APP_DIR")" \
  -x 'voltex/.venv/bin/*' \
  -x 'voltex/.venv/lib/*' \
  -x 'voltex/.venv/lib64/*' \
  -x 'voltex/.venv/include/*' \
  -x 'voltex/.venv/share/*' \
  -x '*/__pycache__/*' \
  -x '*.pyc' \
  -x 'voltex/.pytest_cache/*'

unzip -t "$TARGET" >/dev/null
printf '%s\n' "$TARGET"
