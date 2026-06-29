from agents.base_agent import BaseAgent
import asyncio
from services.memory_service import (
    create_session,
    get_session,
    add_turn,
    get_history_for_gemini,
    get_memory_context,
)
from schemas.memory_schema import MemoryChatResponse


class MemoryAgent(BaseAgent):
    """
    Agent conversationnel avec mémoire court terme.
    Se souvient de tout ce qui a été dit dans une session.
    Peut enrichir ses réponses avec la mémoire long terme.
    """

    def __init__(self):
        super().__init__()
        print("MemoryAgent initialisé")

    async def chat(self, message: str, session_id: str = None) -> MemoryChatResponse:
        """
        Répond à un message en tenant compte de l'historique de la session.
        Si session_id est None, crée une nouvelle session.
        """

        # ── ÉTAPE 1 : RÉCUPÉRER OU CRÉER LA SESSION ─────────────────
        is_new_session = False

        if session_id:
            session = get_session(session_id)
            if not session:
                # Session ID fourni mais introuvable — on en crée une nouvelle
                print(f"Session {session_id} introuvable — création d'une nouvelle")
                session = create_session()
                session_id = session.session_id
                is_new_session = True
        else:
            session = create_session()
            session_id = session.session_id
            is_new_session = True

        memory_used = not is_new_session and len(session.turns) > 0

        # ── ÉTAPE 2 : RÉCUPÉRER L'HISTORIQUE POUR GEMINI ────────────
        history = get_history_for_gemini(session_id)

        # ── ÉTAPE 3 : ENRICHIR AVEC LA MÉMOIRE LONG TERME ───────────
        # On injecte le contexte long terme dans le system prompt
        long_term_context = get_memory_context(category="tendance", limit=3)

        system_context = f"""Tu es un assistant IA avec mémoire.
Tu te souviens de tout ce qui a été dit dans cette conversation.
Tu peux aussi t'appuyer sur des informations passées pour enrichir tes réponses.

{long_term_context}

Réponds de manière précise, en cohérence avec le contexte de la conversation."""

        # ── ÉTAPE 4 : APPEL GEMINI AVEC CONTEXTE ────────────────────
        # On démarre un chat avec l'historique existant
        chat = self.client.chats.create(model=self.model_name, history=history)

        # On envoie le message (avec contexte système si nouvelle session)
        if is_new_session:
            full_message = f"{system_context}\n\nUtilisateur : {message}"
        else:
            full_message = message

        # Wrapper l'appel synchrone de Gemini pour ne pas bloquer
        response = await asyncio.to_thread(chat.send_message, full_message)
        reply = response.text.strip()

        # ── ÉTAPE 5 : SAUVEGARDER LES NOUVEAUX ÉCHANGES ─────────────
        add_turn(session_id, "user", message)
        add_turn(session_id, "model", reply)

        # Récupérer la session mise à jour pour le compteur
        updated_session = get_session(session_id)
        turn_number = updated_session.total_turns // 2  # Chaque échange = 2 tours

        print(
            f"Session {session_id} — Tour {turn_number} — "
            f"Mémoire utilisée : {memory_used}"
        )

        return MemoryChatResponse(
            response=reply,
            session_id=session_id,
            turn_number=turn_number,
            memory_used=memory_used,
        )
