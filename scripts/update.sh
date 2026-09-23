#!/usr/bin/env bash
# Regenerate the rankings and, if anything changed, commit and push.
#
# Used by the daily GitHub Actions workflow, and can be run by hand:
#   bash scripts/update.sh         # regenerate pages only
#   PUSH=1 bash scripts/update.sh  # regenerate, commit and push
#
# For a local daily run instead of Actions, add a cron entry such as:
#   0 6 * * * cd /path/to/github-top-repos && PUSH=1 bash scripts/update.sh >> update.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
OUT_DIR="${OUT_DIR:-docs}"

echo "==> Generating rankings into ${OUT_DIR}/"
"$PYTHON" scripts/fetch_rankings.py --out "$OUT_DIR"

if [[ "${PUSH:-0}" != "1" ]]; then
  echo "==> PUSH not set; skipping commit."
  exit 0
fi

git config user.name  >/dev/null 2>&1 || git config user.name  "github-actions[bot]"
git config user.email >/dev/null 2>&1 || git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add "$OUT_DIR"
if git diff --cached --quiet; then
  echo "==> No changes to commit."
  exit 0
fi

git commit -m "Update rankings $(date -u +%Y-%m-%d)"
git push
echo "==> Rankings pushed."
