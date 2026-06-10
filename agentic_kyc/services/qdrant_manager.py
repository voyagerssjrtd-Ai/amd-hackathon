from __future__ import annotations

from threading import RLock

from services.qdrant_service import QdrantService


_qdrant_instance: QdrantService | None = None
_qdrant_lock = RLock()


def get_qdrant() -> QdrantService:
    """Return the process-wide Qdrant service.

    Embedded Qdrant allows only one client per storage folder in a process.
    Streamlit reruns can recreate modules, so all tools must go through this
    manager rather than constructing QdrantService directly.
    """

    global _qdrant_instance
    with _qdrant_lock:
        if _qdrant_instance is None:
            instance = QdrantService()
            instance.initialize()
            _qdrant_instance = instance
        return _qdrant_instance
