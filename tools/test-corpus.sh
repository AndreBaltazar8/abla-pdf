#!/usr/bin/env bash
# Builds the corpus of PDFs from other producers and runs the reader over it.
set -eu
dir=${1:-tests/corpus/generated}
font=${CORPUS_FONT:-tests/fixtures/DejaVuSans-Latin.ttf}
nix-shell -p qpdf poppler-utils ghostscript fontconfig dejavu_fonts \
    'python3.withPackages(p: [p.reportlab p.pycairo p.pypdf p.pillow])' \
    --run "python3 -I tools/make-corpus.py '$dir' '$font'"
ls "$dir"/*.pdf | wc -l
