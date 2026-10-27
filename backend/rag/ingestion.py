"""Document ingestion: extract plain text from knowledge-base files.

Supported formats (first version): ``.txt``, ``.md`` and text-based ``.pdf``.
Scanned PDFs need OCR, which is intentionally out of scope.

Two entry points:

* ``load_document(path)``  - strict: raises a specific ``IngestionError``.
* ``ingest_directory(dir)`` - tolerant: a bad file never stops the batch; it is
  logged and reported in ``IngestionResult.failures``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .models import Document

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".txt", ".md", ".pdf"})


class IngestionError(Exception):
    """Base class for all ingestion problems."""


class UnsupportedFileTypeError(IngestionError):
    """The file extension is not one of SUPPORTED_EXTENSIONS."""


class EmptyDocumentError(IngestionError):
    """The file was read successfully but contains no usable text."""


class ExtractionError(IngestionError):
    """The file could not be read or parsed (corrupt, locked, encrypted...)."""


@dataclass(frozen=True)
class IngestionFailure:
    path: str
    reason: str


@dataclass
class IngestionResult:
    documents: list[Document] = field(default_factory=list)
    failures: list[IngestionFailure] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Text normalisation
# --------------------------------------------------------------------------- #
def _normalise(text: str) -> str:
    """Unify newlines, drop NUL characters and trim outer whitespace."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return text.strip()


# --------------------------------------------------------------------------- #
# Extractors (one per format; each returns raw text or raises ExtractionError)
# --------------------------------------------------------------------------- #
def _extract_plain_text(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ExtractionError(f"cannot read file: {exc}") from exc
    # utf-8-sig removes a Windows BOM; cp1252 is a common Windows fallback.
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("cannot decode file as UTF-8 or Windows-1252 text")


def _extract_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("PDF is password-protected")
        pages: list[str] = []
        for number, page in enumerate(reader.pages, start=1):
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:  # one bad page should not lose the rest
                logger.warning("%s: page %d skipped (%s)", path.name, number, exc)
        return "\n\n".join(p.strip() for p in pages if p.strip())
    except ExtractionError:
        raise
    except (PyPdfError, OSError, ValueError, KeyError, TypeError) as exc:
        raise ExtractionError(f"cannot parse PDF: {exc}") from exc
    except Exception as exc:  # pypdf can raise assorted errors on corrupt files
        raise ExtractionError(f"unexpected PDF error: {exc}") from exc


_EXTRACTORS: dict[str, Callable[[Path], str]] = {
    ".txt": _extract_plain_text,
    ".md": _extract_plain_text,
    ".pdf": _extract_pdf,
}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def load_document(path: str | Path, root: str | Path | None = None) -> Document:
    """Extract text from one file.

    ``root`` (optional) is the knowledge-base folder; ``Document.source_path``
    is stored relative to it so identical file names in different sub-folders
    stay distinguishable.

    Raises:
        FileNotFoundError: the path does not exist or is not a file.
        UnsupportedFileTypeError, ExtractionError, EmptyDocumentError.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"not a file: {file_path}")

    suffix = file_path.suffix.lower()
    extractor = _EXTRACTORS.get(suffix)
    if extractor is None:
        raise UnsupportedFileTypeError(
            f"unsupported file type '{suffix or '(none)'}' "
            f"(supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))})"
        )

    text = _normalise(extractor(file_path))
    if not text:
        hint = " (scanned PDFs need OCR, which is not supported yet)" if suffix == ".pdf" else ""
        raise EmptyDocumentError(f"no extractable text{hint}")

    if root is not None:
        try:
            relative = file_path.resolve().relative_to(Path(root).resolve())
        except ValueError:
            relative = Path(file_path.name)
    else:
        relative = Path(file_path.name)

    return Document(
        source=file_path.name,
        source_path=relative.as_posix(),
        file_type=suffix.lstrip("."),
        text=text,
    )


def ingest_directory(directory: str | Path, recursive: bool = True) -> IngestionResult:
    """Load every supported file under ``directory``.

    Per-file problems are logged and recorded in ``result.failures`` instead of
    raising. Files with unsupported extensions are reported as failures too, so
    nothing is silently ignored. Hidden files (names starting with ".") are skipped.

    Raises:
        NotADirectoryError: ``directory`` is missing or not a folder.
    """
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(f"knowledge-base directory not found: {root}")

    result = IngestionResult()
    pattern = root.rglob("*") if recursive else root.glob("*")
    for file_path in sorted(p for p in pattern if p.is_file() and not p.name.startswith(".")):
        rel = file_path.relative_to(root).as_posix()
        try:
            result.documents.append(load_document(file_path, root=root))
        except IngestionError as exc:
            logger.warning("Skipping %s: %s", rel, exc)
            result.failures.append(IngestionFailure(rel, str(exc)))
        except OSError as exc:  # e.g. file locked by another Windows process
            logger.warning("Skipping %s: %s", rel, exc)
            result.failures.append(IngestionFailure(rel, f"I/O error: {exc}"))

    logger.info("Ingested %d document(s); %d skipped", len(result.documents), len(result.failures))
    return result
