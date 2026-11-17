#!/usr/bin/env bash
# Writes tests/corpus/files/hostile-many-values.pdf (48 MB, so it is made here and not kept in the repository): twelve million
# values in a page's content stream and as many in an array object, to see the reader survive them.
#   tools/hostile-many-values.sh [output file]
set -euo pipefail
out=${1:-tests/corpus/files/hostile-many-values.pdf}
many() { awk 'BEGIN { for (i = 0; i < 12000000; i++) printf "0 " }'; }
tmp=$(mktemp)
trap 'rm -f "$tmp" "$offsets"' EXIT
offsets=$(mktemp)
object() { # $1 = number; the body follows on standard input
    stat -c %s "$tmp" >> "$offsets"
    printf '%s 0 obj\n' "$1" >> "$tmp"
    cat >> "$tmp"
    printf '\nendobj\n' >> "$tmp"
}
printf '%%PDF-1.4\n' > "$tmp"
printf '<< /Type /Catalog /Pages 2 0 R >>' | object 1
printf '<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [0 0 300 300] /Resources << /Font << /F1 5 0 R >> >> >>' | object 2
printf '<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>' | object 3
{ printf '<<  /Length 24000006 >>\nstream\n'; many; printf ' BT ET\nendstream'; } | object 4
printf '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>' | object 5
{ printf '['; many; printf ']'; } | object 6
xref=$(stat -c %s "$tmp")
{
    printf 'xref\n0 7\n0000000000 65535 f \n'
    while read -r offset; do printf '%010d 00000 n \n' "$offset"; done < "$offsets"
    printf 'trailer\n<< /Size 7 /Root 1 0 R  >>\nstartxref\n%d\n%%%%EOF\n' "$xref"
} >> "$tmp"
mkdir -p "$(dirname "$out")"
cp "$tmp" "$out"
