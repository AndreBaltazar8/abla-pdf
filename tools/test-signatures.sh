#!/usr/bin/env bash
# Signs generated PDFs with a throwaway self-signed certificate made on the spot, then checks the results with poppler's
# pdfsig, openssl cms and qpdf, with tools/signature-parts.ab's own reading of the ByteRange (the gap is exactly the /Contents
# string; the signature covers the whole file) and has openssl sign the same signed attributes to compare the signature's
# bytes. Then three damaged copies must be refused: a byte flipped inside the covered range, bytes appended after the signed
# ranges (an unsigned update: valid, but not the whole file) and a ByteRange whose gap is not the Contents string. This proves
# the file and CMS structure, not a qualified signature: a self-signed certificate is nobody's identity.
# Build build/sign-file and build/signature-parts from tools/*.ab first, then run inside:
#   nix-shell -p openssl qpdf poppler-utils
set -u
work=${1:-build/signatures}
mkdir -p "$work"
fail=0
note() { echo "FAIL $*"; fail=1; }
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$work/key.pem" 2>/dev/null
openssl req -x509 -new -key "$work/key.pem" -subj "/CN=abla-pdf TEST ONLY - not a qualified certificate" -days 2 -addext "keyUsage=critical,digitalSignature,nonRepudiation" -out "$work/cert.pem" -sha256 2>/dev/null
for name in full object-streams pdfa; do
    in=build/generated/$name.pdf
    out=$work/$name-signed.pdf
    build/sign-file "$in" "$work/key.pem" "$work/cert.pem" "$out" || { note "$name: signing"; continue; }
    head -c "$(stat -c %s "$in")" "$out" | cmp - "$in" || note "$name: not an incremental update"
    qpdf --check "$out" >/dev/null 2>&1 || note "$name: qpdf: $(qpdf --check "$out" 2>&1 | tail -3)"
    report=$(pdfsig -nocert "$out" 2>&1)
    echo "$report" | grep -q "Signature Validation: Signature is Valid" || note "$name: pdfsig: $report"
    echo "$report" | grep -q "Total document signed" || note "$name: pdfsig coverage: $report"
    echo "$report" | grep -q "ETSI.CAdES.detached" || note "$name: pdfsig type: $report"
    build/signature-parts "$out" "$work/$name" > "$work/$name.parts" 2>&1 || note "$name: signature-parts: $(cat "$work/$name.parts")"
    grep -q "coverage: the whole file" "$work/$name.parts" || note "$name: signature-parts coverage: $(cat "$work/$name.parts")"
    openssl cms -verify -inform DER -binary -in "$work/$name.p7s" -content "$work/$name.signed" -noverify -out /dev/null 2>"$work/err" \
        || note "$name: openssl cms: $(cat "$work/err")"
    openssl cms -cmsout -print -inform DER -in "$work/$name.p7s" | grep -q "signingCertificateV2\|id-smime-aa-signingCertificateV2" \
        || note "$name: no signing-certificate-v2 attribute"
    openssl dgst -sha256 -sign "$work/key.pem" -out "$work/$name.openssl-sig" "$work/$name.attrs" || note "$name: openssl sign"
    cmp "$work/$name.sig" "$work/$name.openssl-sig" || note "$name: signature differs from openssl's"
done

# Damaged copies of one signed file must be refused, each by the checks that can see it.
good=$work/full-signed.pdf
size=$(stat -c %s "$good")

flipped=$work/flipped.pdf
cp "$good" "$flipped"
printf 'X' | dd of="$flipped" bs=1 seek=100 conv=notrunc 2>/dev/null
cmp -s "$good" "$flipped" && note "flipped: the mutation changed nothing"
pdfsig -nocert "$flipped" 2>&1 | grep -q "Signature is Valid" && note "flipped: pdfsig accepted a changed byte"
build/signature-parts "$flipped" "$work/flipped" > /dev/null 2>&1 || note "flipped: signature-parts could not read the structure"
openssl cms -verify -inform DER -binary -in "$work/flipped.p7s" -content "$work/flipped.signed" -noverify -out /dev/null 2>/dev/null \
    && note "flipped: openssl cms accepted a changed byte"

appended=$work/appended.pdf
cp "$good" "$appended"
printf '\n%% an unsigned update' >> "$appended"
pdfsig -nocert "$appended" 2>&1 | grep -q "Not total document signed" || note "appended: pdfsig did not say the document is not entirely signed"
build/signature-parts "$appended" "$work/appended" > "$work/appended.parts" 2>&1
[ $? = 10 ] || note "appended: signature-parts did not exit 10"
grep -q "not the whole file" "$work/appended.parts" || note "appended: signature-parts did not say not the whole file"

shifted=$work/shifted.pdf
cp "$good" "$shifted"
range=$(grep -a -o '/ByteRange \[0 [0-9]* ' "$good" | head -1)
first=${range#/ByteRange \[0 }
first=${first% }
LC_ALL=C sed "s|/ByteRange \[0 $first |/ByteRange [0 $((first - 1)) |" "$good" > "$shifted"
cmp -s "$good" "$shifted" && note "shifted: the mutation changed nothing"
build/signature-parts "$shifted" "$work/shifted" > "$work/shifted.parts" 2>&1
[ $? = 11 ] || note "shifted: signature-parts did not refuse a ByteRange that is not the Contents string"

[ $fail = 0 ] && echo "signatures passed: pdfsig, openssl cms, qpdf, tools/signature-parts.ab, byte-identical to openssl's; a changed byte, an unsigned update and a shifted ByteRange are refused (self-signed, not qualified)"
exit $fail
