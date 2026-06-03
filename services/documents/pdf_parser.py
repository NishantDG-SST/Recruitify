from dataclasses import dataclass
from io import BytesIO

try:
    import pdfplumber
except ImportError:  # pragma: no cover - optional dependency
    pdfplumber = None


@dataclass(frozen=True)
class PdfParseResult:
    text: str
    warnings: list[str]


def parse_pdf(content: bytes) -> PdfParseResult:
    if pdfplumber is None:
        return PdfParseResult(text="", warnings=["pdfplumber_not_installed"])

    warnings: list[str] = []
    text_parts: list[str] = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")

    text = "\n".join(text_parts).strip()
    if not text:
        warnings.append("pdf_text_empty")

    return PdfParseResult(text=text, warnings=warnings)
