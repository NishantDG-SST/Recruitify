from dataclasses import dataclass
from io import BytesIO

try:
    import docx
except ImportError:  # pragma: no cover - optional dependency
    docx = None


@dataclass(frozen=True)
class DocxParseResult:
    text: str
    warnings: list[str]


def parse_docx(content: bytes) -> DocxParseResult:
    if docx is None:
        return DocxParseResult(text="", warnings=["python_docx_not_installed"])

    document = docx.Document(BytesIO(content))
    text_parts = [para.text for para in document.paragraphs]
    text = "\n".join(text_parts).strip()
    warnings: list[str] = []
    if not text:
        warnings.append("docx_text_empty")

    return DocxParseResult(text=text, warnings=warnings)
