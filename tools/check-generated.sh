#!/usr/bin/env bash
# Checks the files tests/writer_test.ab wrote with independent tools. Needs qpdf,
# poppler-utils, veraPDF and ghostscript on PATH:
#   nix-shell -p qpdf poppler-utils verapdf ghostscript --run tools/check-generated.sh
set -u
dir=${1:-build/generated}
fail=0
note() { echo "FAIL $*"; fail=1; }
for f in "$dir"/*.pdf; do
    name=$(basename "$f")
    out=$(qpdf --check "$f" 2>&1) || note "$name: qpdf --check: $out"
    echo "$out" | grep -qi "warning" && note "$name: qpdf warnings: $out"
    pdfinfo "$f" >/dev/null 2>"$dir/.err" || note "$name: pdfinfo"
    [ -s "$dir/.err" ] && note "$name: pdfinfo stderr: $(cat "$dir/.err")"
    gs -q -dNOPAUSE -dBATCH -sDEVICE=nullpage "$f" >"$dir/.err" 2>&1 || note "$name: ghostscript: $(cat "$dir/.err")"
    grep -qi "error\|warning" "$dir/.err" && note "$name: ghostscript: $(cat "$dir/.err")"
done
for name in full object-streams uncompressed pdfa; do
    f="$dir/$name.pdf"
    text=$(pdftotext -layout "$f" - 2>"$dir/.err")
    [ -s "$dir/.err" ] && note "$name: pdftotext stderr: $(cat "$dir/.err")"
    for expected in "Olá, São João: ação, coração, pão, mãe, avó, você" "São João, ç" "Linha 79 — açúcar" "parágrafo" "Total com duas colunas"; do
        case "$text" in *"$expected"*) ;; *) note "$name: pdftotext is missing: $expected" ;; esac
    done
    case "$(echo "$text" | tr -d ' \n')" in *"ÁÀÂÃÉÊÍÓÔÕÚÇ€"*) ;; *) note "$name: pdftotext is missing the capitals" ;; esac
    pdffonts "$f" | grep -q "CID TrueType *Identity-H *yes yes yes" || note "$name: font not embedded as a subset with ToUnicode: $(pdffonts "$f")"
    [ "$(pdfimages -list "$f" | tail -n +3 | wc -l)" -ge 3 ] || note "$name: pdfimages"
    pdfinfo "$f" | grep -q "Title: *Documento de ação" || note "$name: title"
    pdfinfo "$f" | grep -q "Author: *André Baltazar" || note "$name: author"
    [ "$(pdfinfo "$f" | awk '/^Pages/{print $2}')" -ge 3 ] || note "$name: pages"
done
text=$(pdftotext "$dir/standard-fonts.pdf" -)
for expected in "Olá, São João" "Times: São João, €10" "Courier: ação"; do
    case "$text" in *"$expected"*) ;; *) note "standard-fonts: missing $expected" ;; esac
done
report=$(verapdf --flavour 2b --format text "$dir/pdfa.pdf" 2>/dev/null)
case "$report" in PASS*) echo "veraPDF 2b: $report" ;; *) note "veraPDF: $report"; verapdf --flavour 2b --format xml "$dir/pdfa.pdf" 2>/dev/null | grep -E '<rule |description' | head -40 ;; esac
rm -f "$dir/.err"
[ $fail = 0 ] && echo "all generated files passed"
exit $fail
