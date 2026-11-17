#!/usr/bin/env bash
# The corpus of PDFs from other producers is committed (tests/corpus/files, with where each came from in tests/corpus/README.md);
# only hostile-many-values.pdf, 48 MB, is made here. Then the reader runs over it (make corpus).
set -eu
dir=${1:-tests/corpus/files}
if [ ! -f "$dir/hostile-many-values.pdf" ]; then bash tools/hostile-many-values.sh "$dir/hostile-many-values.pdf"; fi
ls "$dir"/*.pdf | wc -l
