import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict
from schemas.memory_schema import ConversationSession, ConversationTurn, MemoryEntry

# ── MÉMOIRE COURT TERME ────────────────────────────────────────────
# Stockée en RAM — perdue au redémarrage du serveur
# Structure : {session_id: ConversationSession}
_sessions: Dict[str, ConversationSession] = {}


def create_session() -> ConversationSession:
    """Crée une nouvelle session de conversation"""
    session_id = str(uuid.uuid4())[:8]  # ID court : "a3f9b2c1"
    session = ConversationSession(
        session_id=session_id,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        turns=[],
        total_turns=0,
    )
    _sessions[session_id] = session
    print(f"Nouvelle session créée : {session_id}")
    return session


def get_session(session_id: str) -> Optional[ConversationSession]:
    """Récupère une session existante"""
    return _sessions.get(session_id)


def add_turn(session_id: str, role: str, content: str) -> bool:
    """Ajoute un échange à une session existante"""
    session = _sessions.get(session_id)
    if not session:
        return False

    turn = ConversationTurn(
        role=role,
        content=content,
        timestamp=datetime.now().strftime("%H:%M:%S"),
    )
    session.turns.append(turn)
    session.total_turns = len(session.turns)
    return True


def get_history_for_gemini(session_id: str) -> List[dict]:
    """
    Retourne l'historique au format attendu par Gemini.
    Gemini attend : [{"role": "user", "parts": ["..."]}]
    """
    session = _sessions.get(session_id)
    if not session:
        return []

    history = []
    for turn in session.turns:
        history.append(
            {
                "role": turn.role,
                "parts": [turn.content],
            }
        )
    return history


def list_sessions() -> List[str]:
    """Retourne la liste des IDs de sessions actives"""
    return list(_sessions.keys())


def clear_session(session_id: str) -> bool:
    """Supprime une session"""
    if session_id in _sessions:
        del _sessions[session_id]
        return True
    return False


# ── MÉMOIRE LONG TERME ─────────────────────────────────────────────
# Stockée sur disque — persiste entre les redémarrages
MEMORY_FILE = "memory_store.json"


def _load_long_term() -> List[dict]:
    """Charge la mémoire long terme depuis le fichier JSON"""
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_long_term(entries: List[dict]) -> None:
    """Sauvegarde la mémoire long terme dans le fichier JSON"""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def save_to_long_term(
    category: str, content: str, source: Optional[str] = None, importance: int = 1
) -> MemoryEntry:
    """Sauvegarde une information en mémoire long terme"""
    entries = _load_long_term()

    entry = MemoryEntry(
        entry_id=str(uuid.uuid4())[:8],
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        category=category,
        content=content,
        source=source,
        importance=importance,
    )

    entries.append(entry.model_dump())
    _save_long_term(entries)
    print(f"Mémorisé [{category}] : {content[:60]}...")
    return entry


def get_long_term_memory(
    category: Optional[str] = None, limit: int = 10
) -> List[MemoryEntry]:
    """Récupère les entrées de mémoire long terme"""
    entries = _load_long_term()

    if category:
        entries = [e for e in entries if e.get("category") == category]

    # Trier par importance décroissante, puis par date décroissante
    entries.sort(
        key=lambda x: (-x.get("importance", 1), x.get("created_at", "")), reverse=False
    )
    entries = entries[-limit:]  # Garder les N plus récentes

    return [MemoryEntry(**e) for e in entries]


def get_memory_context(category: str = "tendance", limit: int = 5) -> str:
    """
    Retourne un résumé de la mémoire long terme formaté pour un prompt.
    Utilisé par les agents pour contextualiser leur analyse.
    """
    entries = get_long_term_memory(category=category, limit=limit)

    if not entries:
        return "Aucune mémoire disponible pour cette catégorie."

    lines = [f"MÉMOIRE LONG TERME ({category.upper()}) :"]
    for entry in entries:
        lines.append(f"- [{entry.created_at}] {entry.content}")
    return "\n".join(lines)
