#!/usr/bin/env python3
# Writes PDFs from other producers into a directory, each with what independent
# tools say about it, for tests/corpus_test.ab to compare the reader against.
# Run through tools/test-corpus.sh, which provides the tools.
import io, os, struct, subprocess, sys, zlib, base64

out = sys.argv[1]
fonts = sys.argv[2]  # A TrueType font for producers that embed one.
os.makedirs(out, exist_ok=True)
PT = "Olá São João: ação, coração, pão, mãe, avó, você, açúcar, Évora, Açores, 100 €"
EN = "The quick brown fox jumps over the lazy dog 0123456789"

def path(name):
    return os.path.join(out, name + ".pdf")

def run(*args, **kw):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)

# --- Producers ------------------------------------------------------------

def reportlab_files():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    pdfmetrics.registerFont(TTFont("Body", fonts))
    def draw(name, **kw):
        c = canvas.Canvas(path(name), pagesize=A4, **kw)
        c.setTitle("Relatório " + name)
        c.setAuthor("André")
        c.setFont("Helvetica", 12)
        c.drawString(72, 760, EN)
        c.setFont("Body", 12)
        c.drawString(72, 740, PT)
        c.setFont("Times-Roman", 11)
        c.drawString(72, 720, "Times: São João")
        c.showPage()
        c.setFont("Courier", 10)
        for i in range(30):
            c.drawString(72, 750 - 14 * i, "linha numero %d de texto" % i)
        c.showPage()
        c.save()
    draw("reportlab-compressed", pageCompression=1)
    draw("reportlab-plain", pageCompression=0)
    # An interactive form with every field kind.
    c = canvas.Canvas(path("reportlab-form"), pagesize=A4)
    c.setTitle("Form")
    c.drawString(72, 760, "Form page")
    f = c.acroForm
    f.textfield(name="nome", value="Conceição", x=72, y=700, width=200, height=20, relative=False)
    f.checkbox(name="aceito", checked=True, x=72, y=660, size=20, relative=False)
    f.choice(name="cor", value="azul", options=["azul", "verde"], x=72, y=620, width=100, height=20, relative=False)
    f.radio(name="modo", value="a", selected=True, x=72, y=580, size=20, relative=False)
    f.radio(name="modo", value="b", selected=False, x=100, y=580, size=20, relative=False)
    c.linkURL("https://example.com/", (72, 755, 200, 775), relative=0)
    c.showPage()
    c.save()

def cairo_files():
    import cairo
    def scene(surface):
        ctx = cairo.Context(surface)
        ctx.select_font_face("DejaVu Sans")
        ctx.set_font_size(14)
        ctx.move_to(50, 50)
        ctx.show_text(PT)
        ctx.move_to(50, 80)
        ctx.show_text(EN)
        ctx.rectangle(50, 100, 200, 80)
        ctx.set_source_rgb(0.2, 0.4, 0.8)
        ctx.fill()
        image = cairo.ImageSurface(cairo.FORMAT_RGB24, 32, 32)
        ic = cairo.Context(image)
        ic.set_source_rgb(1, 0, 0)
        ic.paint()
        ctx.set_source_surface(image, 300, 100)
        ctx.paint()
        ctx.show_page()
        ctx.select_font_face("DejaVu Sans")
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(50, 50)
        ctx.show_text("Segunda página")
        ctx.show_page()
    surface = cairo.PDFSurface(path("cairo"), 595, 842)
    scene(surface)
    surface.finish()
    surface = cairo.PDFSurface(path("cairo-14"), 595, 842)
    surface.restrict_to_version(cairo.PDFVersion.VERSION_1_4)
    scene(surface)
    surface.finish()

def ghostscript_files():
    ps = os.path.join(out, "source.ps")
    with open(ps, "w") as f:
        f.write("""%!PS
/Helvetica findfont 14 scalefont setfont
72 700 moveto (Ghostscript text page one) show
/Times-Roman findfont 12 scalefont setfont
72 680 moveto (Second line in Times) show
showpage
/Courier findfont 12 scalefont setfont
72 700 moveto (Page two in Courier) show
showpage
""")
    base = ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite"]
    run(*base, "-sOutputFile=" + path("gs-default"), ps)
    run(*base, "-dCompatibilityLevel=1.3", "-sOutputFile=" + path("gs-13"), ps)
    run(*base, "-dCompatibilityLevel=1.7", "-dPDFSETTINGS=/ebook", "-sOutputFile=" + path("gs-17"), ps)
    run(*base, "-dNOPDFMARK", "-dCompressPages=false", "-sOutputFile=" + path("gs-uncompressed"), ps)
    os.remove(ps)

def transforms():
    src = path("reportlab-compressed")
    q = lambda name, *args: run("qpdf", *args, src, path(name))
    q("qpdf-objstm", "--object-streams=generate")
    q("qpdf-linearized", "--linearize")
    q("qpdf-qdf", "--qdf", "--object-streams=disable")
    q("qpdf-nocompress", "--stream-data=uncompress")
    run("qpdf", "--object-streams=generate", "--linearize", path("cairo"), path("qpdf-cairo-objstm"))
    run("pdftocairo", "-pdf", src, path("poppler-cairo"))
    run("pdfunite", path("gs-default"), src, path("poppler-unite"))

def encrypted():
    src = path("reportlab-compressed")
    for name, *args in [
        ("enc-rc4-40", "40"),
        ("enc-rc4-128", "128", "--use-aes=n"),
        ("enc-aes-128", "128", "--use-aes=y"),
        ("enc-aes-256", "256"),
    ]:
        extra = ["--allow-weak-crypto"] if "256" not in args else []
        run("qpdf", *extra, "--encrypt", "", "owner", *args, "--", src, path(name))
        run("qpdf", *extra, "--encrypt", "secret", "owner", *args, "--", src, path(name + "-pw"))
    run("qpdf", "--allow-weak-crypto", "--encrypt", "", "owner", "128", "--use-aes=y", "--cleartext-metadata", "--", src, path("enc-aes-128-clearmeta"))

def incremental():
    # pypdf can append an incremental update; the old content stays in the file.
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject
    w = PdfWriter(path("gs-default"), incremental=True)
    w.add_metadata({"/Title": "Título atualizado"})
    page = w.pages[0]
    content = DecodedStreamObject()
    content.set_data(b"BT /F9 12 Tf 72 500 Td (Replaced by an update) Tj ET")
    page[NameObject("/Contents")] = w._add_object(content)
    from pypdf.generic import DictionaryObject
    resources = DictionaryObject()
    fonts = DictionaryObject()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    fonts[NameObject("/F9")] = font
    resources[NameObject("/Font")] = fonts
    page[NameObject("/Resources")] = resources
    with open(path("pypdf-incremental"), "wb") as f:
        w.write(f)

    # Annotations and a filled form field through pypdf.
    from pypdf.annotations import FreeText, Text
    r = PdfReader(path("reportlab-form"))
    w = PdfWriter(clone_from=r)
    w.add_annotation(0, FreeText(text="Nota com acentuação", rect=(50, 50, 300, 100)))
    w.add_annotation(0, Text(text="Comentário", rect=(320, 50, 350, 80)))
    w.update_page_form_field_values(w.pages[0], {"nome": "Inês Conceição"}, auto_regenerate=False)
    with open(path("pypdf-annotated"), "wb") as f:
        w.write(f)

# --- Written by hand: what no producer here makes on request ---------------

def assemble(objects, trailer_extra="", xref=True, header=b"%PDF-1.4\n"):
    body = bytearray(header)
    offsets = []
    for i, obj in enumerate(objects):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % (i + 1) + obj + b"\nendobj\n"
    at = len(body)
    if xref:
        body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
        for o in offsets:
            body += b"%010d 00000 n \n" % o
        body += b"trailer\n<< /Size %d /Root 1 0 R %s >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, trailer_extra.encode(), at)
    else:
        body += b"trailer\n<< /Size %d /Root 1 0 R %s >>\n" % (len(objects) + 1, trailer_extra.encode())
    return bytes(body)

def simple_doc(stream_obj, text_ops=None):
    return [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [0 0 300 300] /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>",
        stream_obj,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]

CONTENT = b"BT /F1 12 Tf 20 200 Td (Hand written text) Tj ET"

def lzw_encode(data):
    table = {bytes([i]): i for i in range(256)}
    next_code = 258
    width = 9
    bits = 0
    count = 0
    out = bytearray()
    def put(code):
        nonlocal bits, count
        bits = (bits << width) | code
        count += width
        while count >= 8:
            out.append((bits >> (count - 8)) & 255)
            count -= 8
    put(256)
    w = b""
    for b in data:
        wb = w + bytes([b])
        if wb in table:
            w = wb
        else:
            put(table[w])
            table[wb] = next_code
            next_code += 1
            if next_code + 1 >= (1 << width) and width < 12:
                width += 1
            w = bytes([b])
    if w:
        put(table[w])
    put(257)
    if count:
        out.append((bits << (8 - count)) & 255)
    return bytes(out)

def a85(data):
    return base64.a85encode(data) + b"~>"

def hand_files():
    def stream(data, entries=b""):
        return b"<< " + entries + b" /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"
    write = lambda name, data: open(path(name), "wb").write(data)
    write("hand-lzw", assemble(simple_doc(stream(lzw_encode(CONTENT), b"/Filter /LZWDecode"))))
    write("hand-a85", assemble(simple_doc(stream(a85(CONTENT), b"/Filter /ASCII85Decode"))))
    write("hand-hex", assemble(simple_doc(stream(CONTENT.hex().encode() + b">", b"/Filter /ASCIIHexDecode"))))
    rl = bytes([len(CONTENT) - 1]) + CONTENT + b"\x80"
    write("hand-rl", assemble(simple_doc(stream(rl, b"/Filter /RunLengthDecode"))))
    chain = a85(zlib.compress(CONTENT))
    write("hand-chain", assemble(simple_doc(stream(chain, b"/Filter [/ASCII85Decode /FlateDecode]"))))
    # PNG predictor over Flate, with Up filter rows.
    columns = 8
    rows = bytearray()
    previous = bytes(columns)
    padded = CONTENT + b" " * (-len(CONTENT) % columns)
    for i in range(0, len(padded), columns):
        row = padded[i:i + columns]
        rows.append(2)
        rows += bytes((row[k] - previous[k]) & 255 for k in range(columns))
        previous = row
    write("hand-predictor", assemble(simple_doc(stream(zlib.compress(bytes(rows)),
        b"/Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns 8 >>"))))
    # Damage that readers must survive.
    good = assemble(simple_doc(stream(CONTENT)))
    write("broken-no-xref", assemble(simple_doc(stream(CONTENT)), xref=False))
    write("broken-bad-startxref", good.replace(b"startxref\n", b"startxref\n99"))
    write("broken-truncated", good[:good.rindex(b"xref\n0")])
    write("broken-junk-before", b"\n\njunk before the header\n" + good)
    write("broken-wrong-length", assemble(simple_doc(b"<< /Length 3 >>\nstream\n" + CONTENT + b"\nendstream")))
    indirect = simple_doc(b"<< /Length 6 0 R >>\nstream\n" + CONTENT + b"\nendstream") + [b"%d" % len(CONTENT)]
    write("hand-indirect-length", assemble(indirect))
    # Inline image, and a page inheriting everything from its parent.
    inline = b"q 10 0 0 10 50 50 cm BI /W 2 /H 2 /CS /G /BPC 8 ID \x00\xff\xff\x00 EI Q " + CONTENT
    write("hand-inline-image", assemble(simple_doc(stream(inline))))
    # Text in odd operators: quote, TJ with kerning, Tm, Tw and a rotated matrix.
    ops = (b"BT /F1 12 Tf 14 TL 20 250 Td (First) Tj T* (Second) Tj (Third) ' "
           b"1 0 (Fourth line) \" [(Ke) 120 (rn) -300 (ed)] TJ ET "
           b"BT /F1 10 Tf 0 1 -1 0 280 20 Tm (Rotated) Tj ET")
    write("hand-operators", assemble(simple_doc(stream(ops))))
    # Hostile structures.
    loop = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [2 0 R 3 0 R] /Count 2 /Parent 2 0 R >>",
            b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << >> >>",
            stream(b"q Q"),
            ]
    write("hostile-page-loop", assemble(loop))
    deep = b"[" * 100000
    write("hostile-deep-array", assemble(simple_doc(stream(CONTENT)) + [deep]))
    selfform = [b"<< /Type /Catalog /Pages 2 0 R >>",
                b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /XObject << /X 5 0 R >> >> >>",
                stream(b"/X Do"),
                b"<< /Type /XObject /Subtype /Form /BBox [0 0 1 1] /Resources << /XObject << /X 5 0 R >> >> /Length 11 >>\nstream\n/X Do /X Do\nendstream"]
    write("hostile-form-recursion", assemble(selfform))
    bomb = zlib.compress(b"\0" * (300 * 1024 * 1024), 9)
    write("hostile-flate-bomb", assemble(simple_doc(stream(bomb, b"/Filter /FlateDecode"))))
    lengthchain = [b"<< /Type /Catalog /Pages 2 0 R >>",
                   b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                   b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>"]
    for i in range(4, 3000):
        lengthchain.append(b"<< /Length %d 0 R >>\nstream\nx\nendstream" % (i + 1))
    write("hostile-length-chain", assemble(lengthchain))

    # Values by the million, in an array and between content operators.
    many = b"0 " * 12000000
    write("hostile-many-values", assemble(simple_doc(stream(many + b" BT ET")) + [b"[" + many + b"]"]))
    # Forms that each draw the next many times: far more operators than bytes.
    fans = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /XObject << /X 5 0 R >> >> >>",
            stream(b"/X Do " * 50)]
    for i in range(5, 16):
        body = b"/X Do " * 50 if i < 15 else b"BT ET"
        fans.append(b"<< /Type /XObject /Subtype /Form /Resources << /XObject << /X %d 0 R >> >> /Length %d >>\nstream\n" % (i + 1, len(body)) + body + b"\nendstream")
    write("hostile-form-fan", assemble(fans))
    # Many fonts, each with a large ToUnicode map.
    cmap = b"1 beginbfrange <0000> <FFFF> <0000> endbfrange endcmap"
    fonts_doc = [b"<< /Type /Catalog /Pages 2 0 R >>",
                 b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"]
    entries = b" ".join(b"/F%d %d 0 R" % (i, i + 6) for i in range(300))
    uses = b" ".join(b"/F%d 9 Tf" % i for i in range(300))
    fonts_doc.append(b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << " + entries + b" >> >> >>")
    fonts_doc.append(stream(b"BT " + uses + b" ET"))
    fonts_doc.append(stream(cmap))
    fonts_doc.append(b"null")
    for i in range(300):
        fonts_doc.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /X /ToUnicode 5 0 R >>")
    write("hostile-many-cmaps", assemble(fonts_doc))

def image_files():
    """Images with the pixels Pillow reads from them, for tests/image_test.ab."""
    from PIL import Image
    d = os.path.join(out, "images")
    os.makedirs(d, exist_ok=True)
    w, h = 13, 7
    rgb = Image.new("RGB", (w, h))
    rgb.putdata([(x * 19, y * 35, (x + y) * 12) for y in range(h) for x in range(w)])
    rgba = Image.new("RGBA", (w, h))
    rgba.putdata([(x * 19, y * 35, 100, (x * y * 7) & 255) for y in range(h) for x in range(w)])
    variants = {
        "rgb": rgb,
        "rgba": rgba,
        "gray": rgb.convert("L"),
        "gray-alpha": rgba.convert("LA"),
        "palette": rgb.convert("P", palette=Image.ADAPTIVE, colors=16),
        "one-bit": rgb.convert("1"),
    }
    def record(name, image):
        image = image.convert("RGBA")
        open(os.path.join(d, name + ".rgba"), "wb").write(image.tobytes())
    for name, image in variants.items():
        image.save(os.path.join(d, name + ".png"))
        record(name, Image.open(os.path.join(d, name + ".png")))
    gray16 = Image.new("I;16", (w, h))
    gray16.putdata([x * 5000 for y in range(h) for x in range(w)])
    gray16.save(os.path.join(d, "gray16.png"))
    # Pillow reduces 16-bit to its top byte with a right shift, as we do.
    open(os.path.join(d, "gray16.rgba"), "wb").write(bytes(
        v for y in range(h) for x in range(w) for v in ((x * 5000) >> 8, (x * 5000) >> 8, (x * 5000) >> 8, 255)))
    # Adam7, which Pillow reads but doesn't write.
    passes = [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
    raw = bytearray()
    pixels = rgb.tobytes()
    for x0, y0, dx, dy in passes:
        for y in range(y0, h, dy):
            row = bytearray()
            for x in range(x0, w, dx):
                row += pixels[(y * w + x) * 3:(y * w + x) * 3 + 3]
            if row:
                raw.append(0)
                raw += row
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 1)) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")
    open(os.path.join(d, "interlaced.png"), "wb").write(png)
    record("interlaced", Image.open(os.path.join(d, "interlaced.png")))
    rgb.resize((64, 48)).save(os.path.join(d, "photo.jpg"), quality=90)
    rgb.resize((64, 48)).convert("L").save(os.path.join(d, "photo-gray.jpg"))
    rgb.resize((64, 48)).convert("CMYK").save(os.path.join(d, "photo-cmyk.jpg"))

def describe():
    """What poppler and qpdf say about each file, for the reader to match."""
    from pypdf import PdfReader
    for name in sorted(os.listdir(out)):
        if not name.endswith(".pdf"):
            continue
        p = os.path.join(out, name)
        stem = p[:-4]
        password = "secret" if name.endswith("-pw.pdf") else None
        pw = ["-upw", password] if password else []
        hostile = name.startswith("hostile-")
        meta = {}
        if not hostile:
            info = subprocess.run(["pdfinfo", *pw, p], capture_output=True, text=True)
            for line in info.stdout.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = subprocess.run(["pdftotext", *pw, p, "-"], capture_output=True).stdout
            open(stem + ".txt", "wb").write(text)
            images = subprocess.run(["pdfimages", *pw, "-list", p], capture_output=True, text=True).stdout.splitlines()[2:]
            meta["images"] = str(sum(1 for line in images if " image " in line))
            fields = {}
            try:
                r = PdfReader(p, password=password)
                fields = r.get_fields() or {}
                annots = sum(len(page.get("/Annots") or []) for page in r.pages)
                meta["annots"] = str(annots)
            except Exception:
                meta["annots"] = "?"
            with open(stem + ".fields", "w") as f:
                for k, v in fields.items():
                    value = v.get("/V", "")
                    f.write("%s\t%s\n" % (k, value))
        with open(stem + ".meta", "w") as f:
            for k in ("Pages", "Title", "Author", "images", "annots"):
                f.write("%s\t%s\n" % (k, meta.get(k, "")))
            if password:
                f.write("Password\t%s\n" % password)

reportlab_files()
cairo_files()
ghostscript_files()
transforms()
encrypted()
incremental()
hand_files()
image_files()
describe()
