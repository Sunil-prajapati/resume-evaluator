import docx
import pytest
from pypdf import PdfWriter

from resume_evaluator.errors import NoReadableTextError, ParseError, UnsupportedFormatError
from resume_evaluator.parser import extract_text, normalise

LONG_LINES = [
    "Senior Python Developer with five years of experience building backend services.",
    "Skills: Python, FastAPI, PostgreSQL, Docker, AWS and CI/CD pipelines.",
    "Built and deployed a REST API serving 2 million requests per day at Acme Corp.",
]


def make_pdf(path, pages):
    """Write a minimal text PDF by hand (no extra dependency). `pages` is a list of line lists."""
    objects = []  # index 0 -> object 1

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # placeholder, filled below
    pages_obj = add(b"")  # placeholder
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    kids = []
    for lines in pages:
        ops = ["BT", "/F1 11 Tf", "14 TL", "50 750 Td"]
        for line in lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({safe}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page = add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
            b"/Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>" % (pages_obj, content, font)
        )
        kids.append(page)
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj
    kid_refs = " ".join(f"{k} 0 R" for k in kids).encode()
    objects[pages_obj - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kid_refs, len(kids))

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, catalog, xref)
    path.write_bytes(bytes(out))


# ---------------------------------------------------------------- PDF
def test_pdf_text_extracted_across_pages(tmp_path):
    p = tmp_path / "resume.pdf"
    make_pdf(p, [LONG_LINES[:2], LONG_LINES[2:]])
    text = extract_text(p)
    for line in LONG_LINES:
        assert line in text


def test_pdf_with_no_text_raises_no_readable_text(tmp_path):
    p = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(p, "wb") as f:
        writer.write(f)
    with pytest.raises(NoReadableTextError, match="scanned"):
        extract_text(p)


def test_corrupt_pdf_raises_parse_error(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"this is not a pdf at all")
    with pytest.raises(ParseError):
        extract_text(p)


def test_encrypted_pdf_raises_parse_error(tmp_path):
    plain = tmp_path / "plain.pdf"
    make_pdf(plain, [LONG_LINES])
    writer = PdfWriter(clone_from=plain)
    writer.encrypt("secret")
    locked = tmp_path / "locked.pdf"
    with open(locked, "wb") as f:
        writer.write(f)
    with pytest.raises(ParseError, match="password"):
        extract_text(locked)


# ---------------------------------------------------------------- DOCX
def test_docx_paragraphs_and_tables_in_order(tmp_path):
    d = docx.Document()
    d.add_paragraph("PROFESSIONAL SUMMARY")
    d.add_paragraph(LONG_LINES[0])
    table = d.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Skills"
    table.cell(0, 1).text = "Python, FastAPI, PostgreSQL"
    table.cell(1, 0).text = "Cloud"
    table.cell(1, 1).text = "AWS, Docker"
    d.add_paragraph(LONG_LINES[2])
    p = tmp_path / "resume.docx"
    d.save(p)

    text = extract_text(p)
    assert "Skills | Python, FastAPI, PostgreSQL" in text
    assert "Cloud | AWS, Docker" in text
    # table sits between the paragraphs around it
    assert text.index(LONG_LINES[0]) < text.index("Skills |") < text.index(LONG_LINES[2])


def test_docx_merged_cells_not_duplicated(tmp_path):
    d = docx.Document()
    d.add_paragraph(" ".join(LONG_LINES))
    table = d.add_table(rows=1, cols=2)
    merged = table.cell(0, 0).merge(table.cell(0, 1))
    merged.text = "Languages and Tools"
    p = tmp_path / "merged.docx"
    d.save(p)
    assert extract_text(p).count("Languages and Tools") == 1


def test_corrupt_docx_raises_parse_error(tmp_path):
    p = tmp_path / "bad.docx"
    p.write_bytes(b"not a zip")
    with pytest.raises(ParseError):
        extract_text(p)


def test_short_docx_raises_no_readable_text(tmp_path):
    d = docx.Document()
    d.add_paragraph("Hi")
    p = tmp_path / "tiny.docx"
    d.save(p)
    with pytest.raises(NoReadableTextError):
        extract_text(p)


# ---------------------------------------------------------------- dispatch / errors
def test_txt_is_unsupported(tmp_path):
    p = tmp_path / "resume.txt"
    p.write_text("x" * 500)
    with pytest.raises(UnsupportedFormatError, match=r"\.pdf and \.docx"):
        extract_text(p)


def test_old_doc_gives_helpful_message(tmp_path):
    p = tmp_path / "resume.doc"
    p.write_bytes(b"x")
    with pytest.raises(UnsupportedFormatError, match="Save the resume as .docx"):
        extract_text(p)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_text(tmp_path / "nope.pdf")


def test_extension_check_is_case_insensitive(tmp_path):
    p = tmp_path / "RESUME.PDF"
    make_pdf(p, [LONG_LINES])
    assert LONG_LINES[0] in extract_text(p)


# ---------------------------------------------------------------- normalise
def test_normalise_cleans_whitespace():
    raw = "a\xa0b  \t c  \r\n\r\n\r\n\r\nline2   \x00\n"
    assert normalise(raw) == "a b c\n\nline2"
