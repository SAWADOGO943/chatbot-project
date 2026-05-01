from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ConversationTurn(BaseModel):
    """Un échange dans une conversation"""
    role: str          # "user" ou "model"
    content: str       # Le texte du message
    timestamp: str     # Heure du message

class ConversationSession(BaseModel):
    """Une session de conversation avec son historique"""
    session_id: str              # Identifiant unique de la session
    created_at: str              # Date de création
    turns: List[ConversationTurn]  # Tous les échanges
    total_turns: int             # Nombre d'échanges total

class MemoryChatRequest(BaseModel):
    """Requête pour le chat avec mémoire"""
    message: str                         # Le message de l'utilisateur
    session_id: Optional[str] = None     # ID de session (None = nouvelle session)

class MemoryChatResponse(BaseModel):
    """Réponse du chat avec mémoire"""
    reply: str                   # La réponse de l'agent
    session_id: str              # L'ID de session (pour les appels suivants)
    turn_number: int             # Numéro de l'échange dans la session
    memory_used: bool            # True si l'agent a utilisé du contexte passé

class MemoryEntry(BaseModel):
    """Une entrée en mémoire long terme"""
    entry_id: str                # Identifiant unique
    created_at: str              # Date de création
    category: str                # "rapport_news", "tendance", "fait_important"
    content: str                 # Le contenu mémorisé
    source: Optional[str] = None # D'où vient cette information
    importance: int = 1          # Score d'importance (1 à 5)