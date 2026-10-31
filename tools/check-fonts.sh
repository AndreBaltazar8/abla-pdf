#!/usr/bin/env bash
# Embeds whole real-world fonts through examples/invoice.ab and checks the output
# with poppler and qpdf. Needs build/invoice, built from that example, and nix.
set -u
fail=0
note() { echo "FAIL $*"; fail=1; }
mkdir -p build/fonts
liberation=$(nix-build '<nixpkgs>' -A liberation_ttf --no-out-link)/share/fonts/truetype
dejavu=$(nix-build '<nixpkgs>' -A dejavu_fonts.minimal --no-out-link)/share/fonts/truetype
for font in "$liberation/LiberationSans-Regular.ttf" "$liberation/LiberationSerif-BoldItalic.ttf" \
            "$liberation/LiberationMono-Regular.ttf" "$dejavu/DejaVuSans.ttf"; do
    name=$(basename "$font" .ttf)
    out=build/fonts/$name.pdf
    build/invoice "$font" "$out" || { note "$name: example failed"; continue; }
    qpdf --check "$out" >/dev/null 2>&1 || note "$name: qpdf: $(qpdf --check "$out" 2>&1 | tail -2)"
    text=$(pdftotext -layout "$out" - 2>&1)
    for expected in "Associação de Educação Física de São João" "Coração, ação, língua, Évora, Açores" "Prestação de serviços" "300,00 €"; do
        case "$(echo "$text" | tr -s ' ' )" in *"$expected"*) ;; *) note "$name: pdftotext is missing '$expected': $text" ;; esac
    done
    pdffonts "$out" | grep -q "CID TrueType *Identity-H *yes yes yes" || note "$name: $(pdffonts "$out")"
    size=$(stat -c %s "$out")
    original=$(stat -L -c %s "$font")
    [ "$size" -lt $((original / 4)) ] || note "$name: $size bytes from a $original byte font: not subset"
    echo "$name: font $original bytes, file $size bytes"
done
[ $fail = 0 ] && echo "real fonts passed"
exit $fail
