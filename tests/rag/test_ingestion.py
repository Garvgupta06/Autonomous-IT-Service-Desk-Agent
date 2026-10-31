import io

import pytest
from pypdf import PdfWriter

from backend.rag.ingestion import (
    EmptyDocumentError,
    ExtractionError,
    UnsupportedFileTypeError,
    ingest_directory,
    load_document,
)


def make_text_pdf(text: str) -> bytes:
    """Build a tiny valid one-page text PDF (no extra dependencies needed)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def test_txt_and_md_are_extracted_and_normalised(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"\xef\xbb\xbfLine one\r\nLine two\r\n")
    (tmp_path / "b.md").write_text("# Title\n\nBody", encoding="utf-8")
    a = load_document(tmp_path / "a.txt")
    assert a.text == "Line one\nLine two"            # BOM removed, CRLF -> LF
    assert (a.source, a.file_type) == ("a.txt", "txt")
    assert load_document(tmp_path / "b.md").text.startswith("# Title")


def test_windows_1252_text_falls_back(tmp_path):
    (tmp_path / "w.txt").write_bytes("café".encode("cp1252"))
    assert load_document(tmp_path / "w.txt").text == "café"


def test_pdf_text_is_extracted(tmp_path):
    (tmp_path / "guide.pdf").write_bytes(make_text_pdf("Reset your VPN password"))
    doc = load_document(tmp_path / "guide.pdf")
    assert "VPN" in doc.text and doc.file_type == "pdf"


def test_empty_and_whitespace_files_raise_empty_error(tmp_path):
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / "blank.md").write_text("  \n\n ")
    with pytest.raises(EmptyDocumentError):
        load_document(tmp_path / "empty.txt")
    with pytest.raises(EmptyDocumentError):
        load_document(tmp_path / "blank.md")


def test_pdf_without_text_raises_empty_error(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)   # like a scanned page: no text layer
    with open(tmp_path / "scan.pdf", "wb") as fh:
        writer.write(fh)
    with pytest.raises(EmptyDocumentError):
        load_document(tmp_path / "scan.pdf")


def test_corrupt_pdf_raises_extraction_error(tmp_path):
    (tmp_path / "bad.pdf").write_bytes(b"this is not a pdf")
    with pytest.raises(ExtractionError):
        load_document(tmp_path / "bad.pdf")


def test_unsupported_and_missing_files(tmp_path):
    (tmp_path / "tool.exe").write_bytes(b"MZ")
    with pytest.raises(UnsupportedFileTypeError):
        load_document(tmp_path / "tool.exe")
    with pytest.raises(FileNotFoundError):
        load_document(tmp_path / "missing.txt")


def test_ingest_directory_keeps_going_and_reports_failures(tmp_path):
    (tmp_path / "ok.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.md").write_text("nested doc")
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / "tool.exe").write_bytes(b"MZ")
    (tmp_path / "bad.pdf").write_bytes(b"garbage")

    result = ingest_directory(tmp_path)

    assert sorted(d.source_path for d in result.documents) == ["ok.txt", "sub/nested.md"]
    assert sorted(f.path for f in result.failures) == ["bad.pdf", "empty.txt", "tool.exe"]


def test_ingest_directory_missing_folder_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        ingest_directory(tmp_path / "nope")
