"""Turn a resume file (.pdf / .docx) into clean plain text."""

import re
import sys
from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from . import config
from .errors import NoReadableTextError, ParseError, ResumeEvaluatorError, UnsupportedFormatError

SUPPORTED = (".pdf", ".docx")


def extract_text(path: str | Path) -> str:
    """Read a PDF or DOCX and return normalised text.

    Raises:
        FileNotFoundError: the path does not exist.
        UnsupportedFormatError: not a .pdf or .docx.
        ParseError: corrupt or password-protected file.
        NoReadableTextError: too little text (likely a scanned PDF).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Resume not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raw = _read_pdf(path)
    elif suffix == ".docx":
        raw = _read_docx(path)
    elif suffix == ".doc":
        raise UnsupportedFormatError("Old .doc files are not supported. Save the resume as .docx and try again.")
    else:
        raise UnsupportedFormatError(f"Unsupported file type '{suffix}'. Only .pdf and .docx are supported.")

    text = normalise(raw)
    if len(text) < config.MIN_RESUME_CHARS:
        raise NoReadableTextError(
            f"Only {len(text)} characters of text found (minimum {config.MIN_RESUME_CHARS}). "
            "This may be a scanned PDF; OCR is not supported in v1."
        )
    return text


def normalise(text: str) -> str:
    """Tidy extracted text without changing its content."""
    text = text.replace("\x00", "").replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------- PDF
def _read_pdf(path: Path) -> str:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ParseError("The PDF is password-protected. Remove the password and try again.")
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except ParseError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError) as e:
        raise ParseError(f"Could not read the PDF ({type(e).__name__}: {e}).") from e


# --------------------------------------------------------------------------- DOCX
def _read_docx(path: Path) -> str:
    try:
        document = docx.Document(str(path))
    except Exception as e:  # python-docx raises several unrelated types on bad zips/xml
        raise ParseError(f"Could not read the DOCX ({type(e).__name__}: {e}).") from e

    parts: list[str] = []
    # Walk the body in document order so tables stay between the paragraphs around them.
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            parts.append(Paragraph(child, document).text)
        elif tag == "tbl":
            parts.extend(_table_lines(Table(child, document)))
    return "\n".join(parts)


def _table_lines(table: Table) -> list[str]:
    """One line per row, cells joined by ' | '. Merged cells repeat; drop consecutive duplicates."""
    lines = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            text = " ".join(cell.text.split())
            if text and (not cells or cells[-1] != text):
                cells.append(text)
        if cells:
            lines.append(" | ".join(cells))
    return lines


if __name__ == "__main__":
    # Manual check:  uv run python -m resume_evaluator.parser samples/my_resume.pdf
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m resume_evaluator.parser <resume.pdf|resume.docx>")
    try:
        print(extract_text(sys.argv[1]))
    except (ResumeEvaluatorError, FileNotFoundError) as e:
        raise SystemExit(f"Error: {e}")
