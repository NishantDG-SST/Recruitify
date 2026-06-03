from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StoredDocument:
    document_id: str
    storage_url: str
    sha256: str


class DocumentStorage:
    def store(self, content: bytes, filename: str, mime_type: str) -> StoredDocument:
        return StoredDocument(document_id="doc_demo", storage_url="", sha256="")

    def fetch(self, document_id: str) -> Optional[bytes]:
        return None
