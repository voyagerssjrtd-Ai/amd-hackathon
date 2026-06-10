from __future__ import annotations

import csv
import hashlib
import os
import uuid
from pathlib import Path

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from sentence_transformers import SentenceTransformer
except ImportError:
    QdrantClient = None
    Distance = None
    PointStruct = None
    VectorParams = None
    SentenceTransformer = None


class QdrantService:
    """Qdrant-backed compliance RAG service.

    Defaults to embedded local Qdrant for hackathon simplicity. For concurrent
    access, set QDRANT_URL and run a Qdrant server instead of using a local path.
    """

    COLLECTION_NAME = "compliance_knowledge"

    def __init__(
        self,
        db_path: str | Path = "database/qdrant",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
    ) -> None:
        self.db_path = Path(os.getenv("QDRANT_PATH", str(db_path)))
        self.qdrant_url = os.getenv("QDRANT_URL", "").strip()
        self.embedding_model = os.getenv("EMBEDDING_MODEL", embedding_model)
        self.client: QdrantClient | None = None
        self.encoder: SentenceTransformer | None = None
        self.vector_size: int | None = None

    def initialize(self) -> None:
        if QdrantClient is None or SentenceTransformer is None:
            raise RuntimeError("qdrant-client and sentence-transformers are required for compliance RAG")
        self.client = self.client or self._create_client()
        self.encoder = self.encoder or SentenceTransformer(self.embedding_model, device="cpu")
        if self.vector_size is None:
            if hasattr(self.encoder, "get_embedding_dimension"):
                self.vector_size = self.encoder.get_embedding_dimension()
            else:
                self.vector_size = self.encoder.get_sentence_embedding_dimension()

        collections = self.client.get_collections()
        existing = {collection.name for collection in collections.collections}
        if self.COLLECTION_NAME not in existing:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    def _create_client(self) -> QdrantClient:
        if self.qdrant_url:
            return QdrantClient(url=self.qdrant_url)
        self.db_path.mkdir(parents=True, exist_ok=True)
        try:
            return QdrantClient(path=str(self.db_path))
        except RuntimeError as exc:
            if "already accessed by another instance" not in str(exc):
                raise
            # Streamlit reruns or parallel terminals can leave embedded Qdrant
            # locked. Keep the demo alive with an in-memory compliance index.
            return QdrantClient(location=":memory:")

    def load_compliance_knowledge(self, knowledge_dir: str | Path) -> int:
        knowledge_dir = Path(knowledge_dir)
        documents: list[dict] = []

        for csv_name, source in [
            ("watchlist.csv", "WATCHLIST"),
            ("blacklist.csv", "BLACKLIST"),
            ("pep.csv", "PEP"),
        ]:
            path = knowledge_dir / csv_name
            if path.exists():
                with path.open(encoding="utf-8") as file:
                    for row in csv.DictReader(file):
                        content = " | ".join(f"{key}: {value}" for key, value in row.items() if value)
                        if content:
                            documents.append(
                                {
                                    "source": source,
                                    "content": content,
                                    "risk": row.get("risk") or row.get("severity") or "MEDIUM",
                                }
                            )

        fraud_file = knowledge_dir / "fraud_cases.csv"
        if fraud_file.exists():
            with fraud_file.open(encoding="utf-8") as file:
                for row in csv.DictReader(file):
                    documents.append(
                        {
                            "source": "FRAUD_CASE",
                            "content": row.get("description", ""),
                            "risk": row.get("risk", "UNKNOWN"),
                        }
                    )

        for filename, source in [("aml_policies.txt", "AML_POLICY"), ("rbi_guidelines.txt", "RBI_GUIDELINE")]:
            path = knowledge_dir / filename
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        documents.append({"source": source, "content": line, "risk": "MEDIUM"})

        return self.index_documents(documents)

    def index_documents(self, documents: list[dict]) -> int:
        self.initialize_if_needed()
        if not documents:
            return 0

        points: list[PointStruct] = []
        for document in documents:
            content = str(document.get("content", "")).strip()
            if not content:
                continue
            embedding = self.encoder.encode(content, normalize_embeddings=True).tolist()
            payload = {
                "source": document.get("source", "UNKNOWN"),
                "content": content,
                "risk": document.get("risk", "UNKNOWN"),
            }
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, stable_document_key(payload)))
            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        if not points:
            return 0
        self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)
        return len(points)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        self.initialize_if_needed()
        if not query.strip():
            return []

        embedding = self.encoder.encode(query, normalize_embeddings=True).tolist()
        results = self.client.search(collection_name=self.COLLECTION_NAME, query_vector=embedding, limit=limit)
        return [
            {
                "score": round(float(result.score), 4),
                "source": result.payload.get("source", "UNKNOWN"),
                "content": result.payload.get("content", ""),
                "risk": result.payload.get("risk", "UNKNOWN"),
            }
            for result in results
        ]

    def count(self) -> int:
        self.initialize_if_needed()
        info = self.client.get_collection(collection_name=self.COLLECTION_NAME)
        return info.points_count

    def delete_collection(self) -> None:
        self.initialize_if_needed()
        collections = self.client.get_collections()
        existing = {collection.name for collection in collections.collections}
        if self.COLLECTION_NAME in existing:
            self.client.delete_collection(collection_name=self.COLLECTION_NAME)

    def initialize_if_needed(self) -> None:
        if self.client is None or self.encoder is None or self.vector_size is None:
            self.initialize()


def stable_document_key(payload: dict) -> str:
    raw = f"{payload.get('source', '')}|{payload.get('risk', '')}|{payload.get('content', '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
