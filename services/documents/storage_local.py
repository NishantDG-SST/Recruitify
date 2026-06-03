import uuid
import hashlib
from dataclasses import dataclass
from pathlib import Path

from services.documents.storage import StoredDocument


@dataclass(frozen=True)
class LocalStorageConfig:
    root_dir: Path


class LocalDocumentStorage:
    def __init__(self, config: LocalStorageConfig) -> None:
        self._root = config.root_dir
        self._root.mkdir(parents=True, exist_ok=True)

    def store(self, content: bytes, filename: str, mime_type: str) -> StoredDocument:
        sha256 = hashlib.sha256(content).hexdigest()
        document_id = str(uuid.uuid4())
        path = self._root / document_id
        path.write_bytes(content)
        return StoredDocument(document_id=document_id, storage_url=str(path), sha256=sha256)

    def fetch(self, document_id: str) -> bytes | None:
        path = self._root / document_id
        if not path.exists():
            return None
        return path.read_bytes()
