from __future__ import annotations
import csv
import uuid
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

def load_compliance_knowledge(
    self,
    knowledge_dir: str | Path,
) -> int:
    """
    Loads AML knowledge and fraud intelligence into Qdrant.

    Indexed:
    - fraud_cases.csv
    - aml_policies.txt
    - rbi_guidelines.txt
    """

    knowledge_dir = Path(knowledge_dir)

    documents: list[dict] = []

    #
    # FRAUD CASES
    #

    fraud_file = knowledge_dir / "fraud_cases.csv"

    if fraud_file.exists():

        with fraud_file.open(
            encoding="utf-8",
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                documents.append(
                    {
                        "source": "FRAUD_CASE",

                        "content":
                            row.get(
                                "description",
                                "",
                            ),

                        "risk":
                            row.get(
                                "risk",
                                "UNKNOWN",
                            ),
                    }
                )

    #
    # AML POLICIES
    #

    aml_file = knowledge_dir / "aml_policies.txt"

    if aml_file.exists():

        for line in aml_file.read_text(
            encoding="utf-8",
        ).splitlines():

            line = line.strip()

            if line:

                documents.append(
                    {
                        "source":
                            "AML_POLICY",

                        "content":
                            line,

                        "risk":
                            "MEDIUM",
                    }
                )

    #
    # RBI GUIDELINES
    #

    rbi_file = knowledge_dir / "rbi_guidelines.txt"

    if rbi_file.exists():

        for line in rbi_file.read_text(
            encoding="utf-8",
        ).splitlines():

            line = line.strip()

            if line:

                documents.append(
                    {
                        "source":
                            "RBI_GUIDELINE",

                        "content":
                            line,

                        "risk":
                            "MEDIUM",
                    }
                )

    return self.index_documents(
        documents,
    )

from sentence_transformers import SentenceTransformer


class QdrantService:
    """
    Local embedded Qdrant service used for RAG.

    Supports:
    - Collection initialization
    - Document indexing
    - Semantic search
    - Collection statistics
    - Collection reset
    """

    COLLECTION_NAME = "compliance_knowledge"

    def __init__(
        self,
        db_path: str | Path = "database/qdrant",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
    ) -> None:

        self.db_path = Path(db_path)

        self.client = QdrantClient(
            path=str(self.db_path),
        )

        self.encoder = SentenceTransformer(
            embedding_model,
            device="cpu",
        )

        self.vector_size = self.encoder.get_sentence_embedding_dimension()

    def initialize(self) -> None:
        """
        Create collection if it does not exist.
        """

        collections = self.client.get_collections()

        existing = {
            collection.name
            for collection in collections.collections
        }

        if self.COLLECTION_NAME not in existing:

            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,

                vectors_config=VectorParams(
                    size=self.vector_size,

                    distance=Distance.COSINE,
                ),
            )

    def index_documents(
        self,
        documents: list[dict],
    ) -> int:
        """
        Index compliance knowledge.

        Expected format:

        [
            {
                "source": "PEP",
                "content": "...",
                "risk": "HIGH",
            }
        ]
        """

        if not documents:
            return 0

        points: list[PointStruct] = []

        for document in documents:

            content = str(
                document.get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            embedding = (
                self.encoder.encode(
                    content,
                    normalize_embeddings=True,
                )
                .tolist()
            )

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

            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),

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
        """
        Semantic search over indexed knowledge.
        """

        if not query.strip():
            return []

        embedding = (
            self.encoder.encode(
                query,
                normalize_embeddings=True,
            )
            .tolist()
        )

        results = self.client.search(
            collection_name=self.COLLECTION_NAME,

            query_vector=embedding,

            limit=limit,
        )

        output: list[dict] = []

        for result in results:

            output.append(
                {
                    "score": round(
                        float(result.score),
                        4,
                    ),

                    "source": result.payload.get(
                        "source",
                        "UNKNOWN",
                    ),

                    "content": result.payload.get(
                        "content",
                        "",
                    ),

                    "risk": result.payload.get(
                        "risk",
                        "UNKNOWN",
                    ),
                }
            )

        return output

    def count(self) -> int:
        """
        Number of indexed records.
        """

        info = self.client.get_collection(
            collection_name=self.COLLECTION_NAME,
        )

        return info.points_count

    def delete_collection(self) -> None:
        """
        Development utility.
        """

        collections = self.client.get_collections()

        existing = {
            collection.name
            for collection in collections.collections
        }

        if self.COLLECTION_NAME in existing:

            self.client.delete_collection(
                collection_name=self.COLLECTION_NAME,
            )