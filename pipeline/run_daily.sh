#!/usr/bin/env bash
# Actualizarea zilnica: REPES -> OCR -> preturi -> pozitie -> analiza zonei -> site + istoric.
set -euo pipefail
cd "$(dirname "$0")/.."
WORK="${WORK:-work}"
mkdir -p "$WORK"
python3 pipeline/fetch.py "$WORK"
python3 pipeline/ocr.py "$WORK/pubs" "$WORK/txt"
find "$WORK/pubs" -name '*.pdf' -delete          # textul e extras; PDF-ul ramane doar la sursa (REPES)
python3 pipeline/parse.py "$WORK"
python3 pipeline/market.py "$WORK"
python3 pipeline/geocode.py "$WORK"
python3 pipeline/geo.py "$WORK" rows2.json
python3 pipeline/zone.py "$WORK"
python3 pipeline/build.py "$WORK" data.json
python3 pipeline/history.py data.json history.json
