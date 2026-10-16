#!/usr/bin/env bash
# Actualizarea zilnica: REPES -> OCR -> preturi -> pozitie -> analiza zonei -> site + istoric.
set -euo pipefail
cd "$(dirname "$0")/.."
WORK="${WORK:-work}"
mkdir -p "$WORK"
step() { echo "== $(date +%H:%M:%S) =="; }
step; python3 pipeline/fetch.py "$WORK"
step; python3 pipeline/ocr.py "$WORK/pubs" "$WORK/txt"
find "$WORK/pubs" -name '*.pdf' -delete          # textul e extras; PDF-ul ramane doar la sursa (REPES)
step; python3 pipeline/parse.py "$WORK"
step; python3 pipeline/market.py "$WORK"
step; python3 pipeline/geocode.py "$WORK"
step; python3 pipeline/geo.py "$WORK" rows2.json
step; python3 pipeline/zone.py "$WORK"
step; python3 pipeline/build.py "$WORK" data.json
step; python3 pipeline/history.py data.json history.json
