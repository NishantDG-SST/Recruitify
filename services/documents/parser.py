from dataclasses import dataclass
from typing import Dict, List

from services.documents.docx_parser import parse_docx
from services.documents.pdf_parser import parse_pdf


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    metadata: Dict[str, str]
    warnings: List[str]


class DocumentParser:
    def parse_pdf(self, content: bytes) -> ParsedDocument:
        parsed = parse_pdf(content)
        return ParsedDocument(text=parsed.text, metadata={}, warnings=parsed.warnings)

    def parse_docx(self, content: bytes) -> ParsedDocument:
        parsed = parse_docx(content)
        return ParsedDocument(text=parsed.text, metadata={}, warnings=parsed.warnings)
