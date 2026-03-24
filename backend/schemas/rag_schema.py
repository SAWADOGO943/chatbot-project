from pydantic import BaseModel
from typing import List, Optional

# ── INDEXATION ─────────────────────────────────────────────────────


class IndexResponse(BaseModel):
    """Retourné après l'indexation des documents"""

    success: bool
    message: str
    documents_indexed: int  # Nombre de chunks créés


# ── REQUÊTE RAG ────────────────────────────────────────────────────


class RAGRequest(BaseModel):
    """Ce que le frontend envoie pour une question RAG"""

    question: str


class SourceChunk(BaseModel):
    """Un extrait de document source"""

    content: str  # Texte du chunk
    source: str  # Nom du fichier d'origine
    page: Optional[int] = None  # Numéro de page (si PDF)


class RAGResponse(BaseModel):
    """Ce que le backend retourne : réponse + sources"""

    answer: str  # Réponse générée par Gemini
    sources: List[SourceChunk]  # Les extraits utilisés pour répondre
    chunks_used: int  # Nombre de chunks récupérés
