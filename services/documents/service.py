from dataclasses import dataclass

from services.documents.parser import DocumentParser, ParsedDocument
from services.documents.storage import DocumentStorage, StoredDocument


@dataclass(frozen=True)
class DocumentIngestResult:
    stored: StoredDocument
    parsed: ParsedDocument


class DocumentService:
    def __init__(self, storage: DocumentStorage, parser: DocumentParser) -> None:
        self._storage = storage
        self._parser = parser

    def ingest(self, content: bytes, filename: str, mime_type: str) -> DocumentIngestResult:
        stored = self._storage.store(content, filename, mime_type)
        if mime_type == "application/pdf":
            parsed = self._parser.parse_pdf(content)
        else:
            parsed = self._parser.parse_docx(content)
        return DocumentIngestResult(stored=stored, parsed=parsed)
