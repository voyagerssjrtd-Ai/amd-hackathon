from services.qdrant_service import QdrantService
_qdrant_instance = None
def get_qdrant() -> QdrantService:
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = QdrantService()
        _qdrant_instance.initialize()
    return _qdrant_instance