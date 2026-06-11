from __future__ import annotations

import csv
import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer

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


def stable_document_key(payload: dict) -> str:
    raw = (
        f"{payload.get('source', '')}|"
        f"{payload.get('risk', '')}|"
        f"{payload.get('content', '')}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class QdrantService:
    """
    Qdrant-backed compliance RAG service.

    Defaults to embedded local Qdrant for hackathon simplicity.
    For concurrent access, set QDRANT_URL and run a Qdrant server.
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

        self.client: Any = None
        self.encoder: Any = None
        self.vector_size: int | None = None

    def initialize(self) -> None:
        if QdrantClient is None or SentenceTransformer is None:
            raise RuntimeError(
                "qdrant-client and sentence-transformers "
                "are required for compliance RAG."
            )

        self.client = self.client or self._create_client()

        self.encoder = self.encoder or SentenceTransformer(
            self.embedding_model,
            device="cpu",
        )

        if self.vector_size is None:
            if hasattr(self.encoder, "get_embedding_dimension"):
                self.vector_size = self.encoder.get_embedding_dimension()
            else:
                self.vector_size = (
                    self.encoder.get_sentence_embedding_dimension()
                )

        collections = self.client.get_collections()
        existing = {c.name for c in collections.collections}

        if self.COLLECTION_NAME not in existing:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    def initialize_if_needed(self) -> None:
        if (
            self.client is None
            or self.encoder is None
            or self.vector_size is None
        ):
            self.initialize()

    def _create_client(self) -> Any:
        if self.qdrant_url:
            return QdrantClient(url=self.qdrant_url)

        self.db_path.mkdir(parents=True, exist_ok=True)

        try:
            return QdrantClient(path=str(self.db_path))

        except RuntimeError as exc:
            if "already accessed by another instance" not in str(exc):
                raise

            print(
                "Embedded Qdrant locked. "
                "Falling back to in-memory mode."
            )

            return QdrantClient(location=":memory:")

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> list[str]:

        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return []

        words = text.split()

        chunks: list[str] = []
        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))

            chunk = " ".join(words[start:end])
            chunks.append(chunk)

            if end >= len(words):
                break

            start = max(0, end - overlap)

        return chunks

    def load_compliance_knowledge(
        self,
        knowledge_dir: str | Path,
    ) -> int:

        self.initialize_if_needed()

        knowledge_dir = Path(knowledge_dir)

        try:
            existing_count = self.count()

            if existing_count > 0:
                return existing_count

        except Exception:
            pass

        documents: list[dict] = []

        # Fraud cases → RAG
        fraud_file = knowledge_dir / "fraud_cases.csv"

        if fraud_file.exists():
            with fraud_file.open(
                encoding="utf-8",
                newline="",
            ) as file:

                reader = csv.DictReader(file)

                for row in reader:
                    text = " ".join(
                        filter(
                            None,
                            [
                                row.get("fraud_type", ""),
                                row.get("description", ""),
                                row.get("red_flags", ""),
                                row.get("mitigation", ""),
                            ],
                        )
                    )

                    documents.append(
                        {
                            "source": "FRAUD_CASE",
                            "content": text,
                            "risk": row.get("risk", "HIGH"),
                        }
                    )

        # Policy documents → RAG
        for filename, source in [
            ("aml_policies.txt", "AML_POLICY"),
            ("rbi_guidelines.txt", "RBI_GUIDELINE"),
        ]:

            path = knowledge_dir / filename

            if not path.exists():
                continue

            text = path.read_text(encoding="utf-8")

            chunks = self.chunk_text(
                text=text,
                chunk_size=500,
                overlap=50,
            )

            for chunk in chunks:
                documents.append(
                    {
                        "source": source,
                        "content": chunk,
                        "risk": "MEDIUM",
                    }
                )

        return self.index_documents(documents)

    def index_documents(
        self,
        documents: list[dict],
    ) -> int:

        self.initialize_if_needed()

        if not documents:
            return 0

        points: list[Any] = []

        for document in documents:

            content = str(
                document.get("content", "")
            ).strip()

            if not content:
                continue

            embedding = self.encoder.encode(
                content,
                normalize_embeddings=True,
            ).tolist()

            payload = {
                "source": document.get(
                    "source",
                    "UNKNOWN",
                ),
                "content": content,
                "risk": document.get(
                    "risk",
                    "UNKNOWN",
                ),
            }

            point_id = stable_document_key(payload)

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        if not points:
            return 0

        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=points,
        )

        return len(points)

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict]:

        self.initialize_if_needed()

        if not query.strip():
            return []

        embedding = self.encoder.encode(
            query,
            normalize_embeddings=True,
        ).tolist()

        try:
            results = self.client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=embedding,
                limit=limit,
            ).points

        except AttributeError:
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=embedding,
                limit=limit,
            )

        return [
            {
                "score": round(
                    float(point.score),
                    4,
                ),
                "source": point.payload.get(
                    "source",
                    "UNKNOWN",
                ),
                "content": point.payload.get(
                    "content",
                    "",
                ),
                "risk": point.payload.get(
                    "risk",
                    "UNKNOWN",
                ),
            }
            for point in results
            if float(point.score) >= 0.70
        ]

    def count(self) -> int:
        self.initialize_if_needed()

        info = self.client.get_collection(
            collection_name=self.COLLECTION_NAME,
        )

        return info.points_count

    def delete_collection(self) -> None:
        self.initialize_if_needed()

        collections = self.client.get_collections()

        existing = {
            c.name for c in collections.collections
        }

        if self.COLLECTION_NAME in existing:
            self.client.delete_collection(
                collection_name=self.COLLECTION_NAME,
            )