# abla-pdf

PDF generation and reading for [Abla](https://github.com/AndreBaltazar8/ablac), in
pure Abla with no native dependencies. Mozilla Public License 2.0.

```abla
import "abla/fs"
import github("AndreBaltazar8/abla-pdf")

fun main: int {
    val doc = PdfDocument(title = "Fatura", author = "André")
    val font = doc.embedFont(path("DejaVuSans.ttf").readText())
    if (!font.ok) return 1
    val page = PdfPage()
    page.text(font, 14.0, 50.0, 780.0, "São João: ação, coração, 100 €")
    doc.addPage(page)
    path("out.pdf").writeText(doc.toBytes())

    val reader = pdfOpen(path("out.pdf").readText())
    if (!reader.ok) return 2
    print(reader.pageText(0))
    0
}
```

Import it without an alias: today an alias doesn't reach what the entry module passes on
with `export import`. All public names start with `Pdf` or `pdf`, so they won't clash.

## Generating

- `PdfDocument`: metadata (`title`, `author`, ... as Info and XMP), `compress`,
  `objectStreams`, `pdfA` (PDF/A-2b), `errors` and `warnings`. `toBytes()` gives the file;
  output is reproducible unless you set dates that differ.
- Fonts: `embedFont(ttf)` embeds a TrueType subset as CIDFontType2 with Identity-H and
  ToUnicode, so any character the font has works, Portuguese included, and text stays
  searchable. `standardFont("Helvetica")` and the other Latin standard fonts hold
  Windows-1252 and aren't embedded. Combining sequences such as `a` + U+0303 are composed.
  CFF OpenType fonts are refused.
- `PdfPage` draws on its own: text (`text`, `textAligned`, `textBox`), paths (`moveTo`,
  `lineTo`, `curveTo`, `rect`, `circle`, `roundedRect`, `stroke`, `fill`, `clip`), colour,
  opacity, transforms, `image`, `link`. `doc.addPage(page)` copies it into the document;
  `page.clear()` starts the next.
- Images: `addJpeg` (passed through), `addPng` (all colour types and depths, interlaced,
  alpha becomes a soft mask), `addRawImage`.
- `PdfTable` with `doc.drawTable`: wrapped cells, alignment, column spans, fills, page
  breaks with repeated headers.

There is no shaping: no kerning, ligatures or complex scripts; each code point maps to
one glyph.

## Reading

`pdfOpen(bytes, PdfReadOptions(password = ...))` returns a `PdfReader`. Check `ok`, then
`error` and `needsPassword`. Damage noticed on the way is in `warnings`, and `repaired`
says the cross-references had to be rebuilt by scanning.

- Structure: classic and stream cross-references, hybrid files, object streams,
  incremental updates, repair of damaged files.
- Filters: Flate, LZW, ASCII85, ASCIIHex, RunLength, PNG and TIFF predictors, chains.
  Image codecs (DCT, JPX, CCITT, JBIG2) aren't decoded: `imageData` returns those bytes
  with their `encoding`.
- `pageTextItems(i)`: UTF-8 text with position, width, size, font and angle. `pageText(i)`:
  the same assembled top to bottom, left to right. Both take `annotations = true` to
  include what annotations show. Unicode comes from ToUnicode, the font's encoding and
  Differences, or the embedded TrueType cmap. CJK predefined CMaps other than the UCS-2
  and UTF-16 ones need a ToUnicode map, or give U+FFFD.
- `pageFills(i)`: filled areas that are upright rectangles (`re`, or four straight lines round
  one), in page coordinates with the fill's lightness from 0 to 1, in drawing order. Barcodes
  and QR codes drawn as vectors come out as these; curves, strokes and other shapes don't.
- `pageImages(i)` and `imageData`; `metadata()`, `xmpMetadata()`, `pdfParseDate`;
  `pageMediaBox`, `pageCropBox`, `pageRotation`, `pageCount`.
- Encrypted files with the standard handler: RC4 40 and 128, AES-128, AES-256 (revisions 5
  and 6), with the user or owner password. Public-key handlers are refused.
- `formFields()` and `pageAnnotations(i)`.

Hostile input: the reader is built not to panic on any input, and fuzzing tests that.
Recursion, decoded bytes, parsed values, pages and operators all have limits in
`PdfReadOptions`; past a limit a read ends with less data and a warning. The defaults fit
Abla's default 1 GiB heap limit. Raising `maxStreamBytes` or `maxNodes` a lot can reach
that limit's panic unless you also raise it with `memorySetLimit`.

## Signing (PAdES B-B)

`pdfSign(file, signer, PdfSignOptions(signedAt = ms, reason = ...))` appends an incremental
update holding an invisible signature field and a CMS detached `ETSI.CAdES.detached`
signature with SHA-256 and the signing-certificate-v2 attribute. `PdfSigner` is an
interface, so the key can stay in a smart card or HSM; `PdfRsaSigner` signs with an RSA key
in memory, of 2048 bits or more, through ablac's `abla/crypto/rsa`, which blinds, works in
constant-time arithmetic and checks each signature before returning it.

`pdfVerifySignatures(file)` reports for each signature whether the byte ranges and digest
hold, whether the RSA signature matches the certificate inside it, and whether the signed
bytes reach the end of the file.

**This is not a qualified signature, and a passing check isn't a legal judgement.** A
qualified electronic signature needs a qualified certificate and signature device, which
this library doesn't provide; it has only been tested with self-generated certificates.
The verifier doesn't build a chain to a trust anchor, check revocation or consult the EU
Trusted List. Not implemented: timestamps and long-term validation (B-T, B-LT, B-LTA),
visible signature appearances, signing encrypted files, verifying ECDSA signatures.

## Testing

`make test` runs the unit tests. `make external` puts generated files through qpdf,
poppler, ghostscript and veraPDF (PDF/A-2b). `make corpus` generates PDFs with cairo,
reportlab, ghostscript, qpdf, pypdf and poppler, plus hand-written damaged and hostile
ones, compares the reader with poppler and pypdf on them, then fuzzes. `make signatures`
signs with a throwaway certificate and checks with pdfsig, openssl cms, qpdf and pyHanko.
All through nix. `tests/fuzz_test.ab` takes a first seed, a seed count and a directory for
longer runs, leaving the input of a crash in `build/fuzz-last.pdf`, and `tools/read-file.ab`
reads one file completely to reproduce it.
