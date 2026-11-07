"""manifest에 고정된 원문 파일을 읽어 정제한 Document로 만든다."""
from pathlib import Path

from app.service.ingest.text_cleaner import clean_text, extract_title
from app.schema.corpus_schema import CorpusManifest
from app.schema.chunk_schema import Document


def load_documents(manifest: CorpusManifest, raw_dir: Path) -> list[Document]:
    """manifest 순서대로 읽는다. 정제 후 비어 있는 문서는 뺀다."""
    documents = []
    for entry in manifest.files:
        raw = (raw_dir / entry.path).read_text(encoding="utf-8")
        text = clean_text(raw)
        if text:
            documents.append(Document(doc_id=entry.path, title=extract_title(raw, entry.path), text=text))
    return documents
