#!/usr/bin/env bash
# Signs generated PDFs with a throwaway self-signed certificate made on the spot,
# then checks the results with poppler's pdfsig, openssl cms, qpdf and pyHanko. This
# proves the file and CMS structure, not a qualified signature: a self-signed
# certificate is nobody's identity.
# Build build/sign-file from tools/sign-file.ab first, then run inside:
#   nix-shell -p openssl qpdf poppler-utils 'python3.withPackages(p: [p.pyhanko p.pyhanko-certvalidator])'
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
    python3 -I - "$out" "$work/$name" <<'PY' || note "$name: extraction"
import re, sys
data = open(sys.argv[1], "rb").read()
m = re.search(rb"/ByteRange \[0 (\d+)\s+(\d+)\s+(\d+)\s*\]", data)
a, b, c = map(int, m.groups())
open(sys.argv[2] + ".signed", "wb").write(data[:a] + data[b:b + c])
open(sys.argv[2] + ".p7s", "wb").write(bytes.fromhex(data[a + 1:b - 1].decode().rstrip("0") + ("0" if len(data[a + 1:b - 1].decode().rstrip("0")) % 2 else "")))
PY
    openssl cms -verify -inform DER -binary -in "$work/$name.p7s" -content "$work/$name.signed" -noverify -out /dev/null 2>"$work/err" \
        || note "$name: openssl cms: $(cat "$work/err")"
    openssl cms -cmsout -print -inform DER -in "$work/$name.p7s" | grep -q "signingCertificateV2\|id-smime-aa-signingCertificateV2" \
        || note "$name: no signing-certificate-v2 attribute"
    if python3 -c 'import pyhanko' 2>/dev/null; then
        python3 -I - "$out" "$work/cert.pem" <<'PY' || note "$name: pyHanko rejected it"
import sys
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.keys import load_cert_from_pemder
from pyhanko_certvalidator import ValidationContext
with open(sys.argv[1], "rb") as f:
    r = PdfFileReader(f)
    sig = r.embedded_signatures[0]
    root = load_cert_from_pemder(sys.argv[2])
    status = validate_pdf_signature(sig, ValidationContext(trust_roots=[root], allow_fetching=False))
    print("pyHanko:", status.summary(), "coverage", status.coverage.name, "intact", status.intact, "valid", status.valid)
    sys.exit(0 if status.intact and status.valid else 1)
PY
    else
        echo "pyHanko not available, skipped"
    fi
done
[ $fail = 0 ] && echo "signatures passed: pdfsig, openssl cms, qpdf, pyHanko (self-signed, not qualified)"
exit $fail
