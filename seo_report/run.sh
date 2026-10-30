#!/usr/bin/env bash
# Fetch → analyze → build the SEO report in one go.
# Usage: seo_report/run.sh WORK_DIR   (WORK_DIR/data と WORK_DIR/lpp-seo-research.html を作る)
set -euo pipefail
WORK="${1:?WORK_DIR required}"
cd "$(dirname "$0")/.."
python3 -m seo_report.fetch_data "$WORK/data"
python3 -W ignore -m seo_report.analyze "$WORK/data" | head -1
python3 -m seo_report.build_report "$WORK/data" "$WORK/lpp-seo-research.html"
