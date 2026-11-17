# The corpus

PDFs from other producers, each with what independent tools say about it (`NAME.meta`: pdfinfo and a form-field count;
`NAME.txt`: pdftotext; `NAME.fields`: form fields and values), for `tests/corpus_test.ab`, `image_test.ab` and `fuzz_test.ab`
(`make corpus`). `images/` has PNGs (with their decoded pixels, `.rgba`) and JPEGs for `image_test.ab`.

It was made once, on 2026-11-17, by a Python script (`git show 4402804:tools/make-corpus.py`; no Python is kept in the
tree) run in nix-shell with qpdf 11.10.1, poppler 25.07.0, Ghostscript 10.06.0, reportlab 4.4.3, pycairo 1.28.0, pypdf 6.1.0 and
Pillow 11.3.0, and is committed so that the tests need none of them:

| Files | Made by |
|---|---|
| `reportlab-*` | reportlab (compressed, plain, an AcroForm with every field kind and a link) |
| `cairo*`, `poppler-cairo` | pycairo's PDF surface (1.5 and 1.4), and pdftocairo |
| `gs-*` | Ghostscript's pdfwrite from a PostScript page pair, at several compatibility levels |
| `qpdf-*`, `enc-*`, `poppler-unite` | qpdf (object streams, linearized, QDF, uncompressed, RC4 40 and 128, AES 128 and 256, with and without a user password) and pdfunite, from the files above |
| `pypdf-*` | pypdf appending incremental updates |
| `hand-*`, `broken-*`, `hostile-*` | written byte by byte by the script: every filter (LZW, ASCII85, hex, run length, chains, PNG predictors), damaged xref tables, and files built to be expensive (bombs, loops, deep arrays, many fonts) |
| `hostile-many-values.pdf` | 48 MB, so made by `tools/hostile-many-values.sh` (`tools/test-corpus.sh`) and not kept |
