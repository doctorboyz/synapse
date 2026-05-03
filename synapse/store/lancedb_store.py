"""LanceDB store — Dense vectors for semantic search

Inspired by: arra-oracle (LanceDB default), SocratiCode (embedding + chunking)
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

try:
    import lancedb
    HAS_LANCEDB = True
except ImportError:
    HAS_LANCEDB = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

log = logging.getLogger("synapse.lancedb")

# nomic-embed-text context window: 8192 tokens ≈ ~30000 chars
# but Ollama API has payload limits, stay safe at 4000 chars per chunk
MAX_CHUNK_CHARS = 4000
CHUNK_OVERLAP = 200


class LanceDBStore:
    def __init__(self, vault_path: Path, embedding_dim: int = 768):
        self.vectors_path = vault_path / "vectors"
        self.vectors_path.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim
        self._db = None
        self._table = None

        if not HAS_LANCEDB:
            raise ImportError("lancedb not installed. Run: pip install lancedb")

        self._db = lancedb.connect(str(self.vectors_path))

    def _chunk_text(self, text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
        """Split text into chunks at paragraph/sentence boundaries.

        Inspired by SocratiCode's 3-tier chunking but simplified for docs.
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 2 > max_chars and current:
                chunks.append(current.strip())
                # Keep last `overlap` chars as context bridge
                if overlap > 0 and len(current) > overlap:
                    current = current[-overlap:] + "\n\n" + para
                else:
                    current = para
            else:
                current = current + "\n\n" + para if current else para

        if current.strip():
            chunks.append(current.strip())

        # If a single paragraph exceeds max, split at sentence boundaries
        final = []
        for chunk in chunks:
            if len(chunk) <= max_chars:
                final.append(chunk)
            else:
                sentences = chunk.replace(". ", ".\n").split("\n")
                sub = ""
                for s in sentences:
                    if len(sub) + len(s) + 1 > max_chars and sub:
                        final.append(sub.strip())
                        sub = s
                    else:
                        sub = sub + " " + s if sub else s
                if sub.strip():
                    final.append(sub.strip())

        return final if final else [text[:max_chars]]

    def _embed_ollama(self, text: str, model: str = "nomic-embed-text") -> list[float]:
        """Get embedding from local Ollama."""
        if not HAS_HTTPX:
            raise ImportError("httpx not installed. Run: pip install httpx")

        # Truncate hard limit
        if len(text) > MAX_CHUNK_CHARS:
            text = text[:MAX_CHUNK_CHARS]

        resp = httpx.post(
            "http://localhost:11434/api/embed",
            json={"model": model, "input": text},
            timeout=30.0,
        )
        if resp.status_code != 200:
            log.warning(f"Ollama embed error {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
        data = resp.json()
        return data["embeddings"][0]

    def _embed(self, text: str, model: str = "nomic-embed-text") -> list[float]:
        """Get embedding vector. Ollama by default."""
        return self._embed_ollama(text, model)

    def add(
        self,
        doc_id: str,
        title: str,
        content: str,
        scope: str = "shared",
        doc_type: str = "learning",
        source_file: Optional[str] = None,
    ) -> None:
        """Add document with vector embedding. Long docs are chunked."""
        chunks = self._chunk_text(content)
        records = []

        for i, chunk in enumerate(chunks):
            try:
                vector = self._embed(chunk)
                chunk_id = f"{doc_id}_c{i}" if len(chunks) > 1 else doc_id
                records.append({
                    "id": chunk_id,
                    "parent_id": doc_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "vector": vector,
                    "title": title,
                    "scope": scope,
                    "doc_type": doc_type,
                    "source_file": source_file or "",
                    "content_hash": hashlib.sha256(chunk.encode()).hexdigest()[:16],
                })
            except Exception as e:
                log.warning(f"Embed failed for chunk {i} of {doc_id}: {e}")
                continue

        if not records:
            return

        try:
            table = self._db.open_table("knowledge")
            table.add(records)
        except Exception:
            self._db.create_table("knowledge", records)

    def search(
        self,
        query: str,
        scope: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Semantic search via dense vectors. Returns [{id, title, scope, score}]."""
        try:
            table = self._db.open_table("knowledge")
        except Exception:
            return []

        try:
            query_vector = self._embed(query)
        except Exception:
            return []

        search = table.search(query_vector).limit(limit)

        if scope:
            search = search.where(f"scope = '{scope}'")

        results = search.to_list()

        # Deduplicate by parent_id — keep best score per document
        seen_parents: dict[str, dict] = {}
        for r in results:
            parent = r.get("parent_id", r["id"])
            if parent not in seen_parents or float(r.get("_distance", 1.0)) < seen_parents[parent].get("score", 1.0):
                seen_parents[parent] = {
                    "id": parent,
                    "title": r["title"],
                    "scope": r["scope"],
                    "doc_type": r["doc_type"],
                    "score": float(r.get("_distance", 1.0)),
                }

        return sorted(seen_parents.values(), key=lambda x: x["score"])

    def delete(self, doc_id: str) -> None:
        """Delete document and all its chunks."""
        try:
            table = self._db.open_table("knowledge")
            table.delete(f"id = '{doc_id}' OR parent_id = '{doc_id}'")
        except Exception:
            pass

    def stats(self) -> dict:
        """Vector store statistics."""
        try:
            table = self._db.open_table("knowledge")
            count = len(table.to_pandas())
        except Exception:
            count = 0

        return {
            "total_vectors": count,
            "embedding_dim": self.embedding_dim,
            "backend": "lancedb",
        }

    def close(self):
        pass