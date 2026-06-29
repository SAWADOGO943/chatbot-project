from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from agents.lc_analysis_agent import LCAnalysisAgent

# Scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Schemas
from schemas.chat_schema import ChatRequest, ChatResponse
from schemas.rag_schema import RAGRequest, RAGResponse, IndexResponse
from schemas.agent_schema import AgentRequest, AgentResponse
from schemas.news_schema import AgentRunResult

# Services et agents
from services.gemini_service import call_gemini
from services.rag_service import RAGService
from agents.text_analysis_agent import TextAnalysisAgent
from agents.news_scraper_agent import NewsScraperAgent

from agents.memory_agent import MemoryAgent
from schemas.memory_schema import MemoryChatRequest, MemoryChatResponse, MemoryEntry
from services.memory_service import (
    list_sessions,
    get_session,
    clear_session,
    get_long_term_memory,
    save_to_long_term,
)
from typing import List

load_dotenv()

# ── VARIABLES GLOBALES ─────────────────────────────────────────────
rag_service: RAGService = None
text_agent: TextAnalysisAgent = None
news_agent: NewsScraperAgent = None
memory_agent: MemoryAgent = None
scheduler: AsyncIOScheduler = None
lc_agent: LCAnalysisAgent = None


# ── LIFESPAN ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service, text_agent, news_agent, scheduler, memory_agent, lc_agent

    print("Démarrage du serveur...")

    # Initialisation des services existants
    rag_service = RAGService()
    if rag_service.is_ready():
        print("RAGService prêt avec des documents déjà indexés")
    else:
        print("RAGService prêt — en attente d'indexation")

    # Initialisation des agents
    text_agent = TextAnalysisAgent()
    print("TextAnalysisAgent prêt")

    memory_agent = MemoryAgent()
    print("MemoryAgent prêt")
    news_agent = NewsScraperAgent()
    print("NewsScraperAgent prêt")

    lc_agent = LCAnalysisAgent()
    print("LCAnalysisAgent (LangChain) prêt")

    # Démarrage du scheduler
    scheduler = AsyncIOScheduler()

    # Planification : toutes les 12 heures
    scheduler.add_job(
        func=news_agent.run,
        trigger=IntervalTrigger(hours=12),
        id="news_agent_job",
        name="Veille tech automatique",
        replace_existing=True,
    )

    scheduler.start()
    print("Scheduler démarré — Agent autonome actif toutes les 12 heures")

    yield  # L'application tourne ici

    # Arrêt propre du scheduler quand le serveur s'arrête
    scheduler.shutdown()
    print("Scheduler arrêté — Serveur en cours d'arrêt")


# ── APPLICATION ────────────────────────────────────────────────────
app = FastAPI(
    title="Chatbot IA + RAG + Agents API",
    description="Backend fullstack avec agents autonomes",
    version="3.0.0",
    lifespan=lifespan,
)

# Exemple de configuration sécurisée
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chatbot-project.vercel.app"],  # Remplacez par votre vrai domaine
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Ne listez que les méthodes nécessaires
    allow_headers=[
        "Content-Type",
        "Authorization",
    ],  # Ne listez que les headers nécessaires
)


# ══════════════════════════════════════════════════════════════════
# ROUTES EXISTANTES — Chat et RAG (inchangées)
# ══════════════════════════════════════════════════════════════════


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Chatbot API v3 is running",
        "rag_ready": rag_service.is_ready() if rag_service else False,
        "scheduler_running": scheduler.running if scheduler else False,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Le message ne peut pas être vide")
    try:
        gemini_reply = await call_gemini(request.message)
        return ChatResponse(reply=gemini_reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.post("/rag/index", response_model=IndexResponse)
async def index_documents():
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAGService non initialisé")
    try:
        result = rag_service.index_documents()
        return IndexResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation: {str(e)}")


@app.post("/rag/query")
async def rag_query(request: RAGRequest):
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAGService non initialisé")
    if not rag_service.is_ready():
        raise HTTPException(status_code=400, detail="Aucun document indexé")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide")
    try:
        response = await rag_service.query(request.question)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur RAG: {str(e)}")


@app.get("/rag/status")
async def rag_status():
    if not rag_service:
        return {"ready": False, "message": "Service non initialisé"}
    return {
        "ready": rag_service.is_ready(),
        "message": "Documents indexés et prêts"
        if rag_service.is_ready()
        else "Aucun document indexé — utilisez POST /rag/index",
    }


# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 13 — Agent d'analyse de texte
# ══════════════════════════════════════════════════════════════════


@app.post("/agent/analyze", response_model=AgentResponse)
async def agent_analyze(request: AgentRequest):
    if not text_agent:
        raise HTTPException(status_code=503, detail="Agent non initialisé")
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")
    if len(request.text) > 5000:
        raise HTTPException(
            status_code=400, detail="Texte trop long. Maximum 5000 caractères."
        )
    try:
        response = await text_agent.run(request.text, request.task)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur agent: {str(e)}")


@app.get("/agent/status")
async def agent_status():
    return {
        "ready": text_agent is not None,
        "agent": "TextAnalysisAgent",
        "tools_available": [
            "analyser_sentiment",
            "extraire_themes",
            "evaluer_complexite",
        ],
    }


# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 14 — Agent autonome de veille tech
# ══════════════════════════════════════════════════════════════════


@app.post("/news-agent/run", response_model=AgentRunResult)
async def news_agent_run():
    """
    Déclenche l'agent manuellement.
    Utile pour tester sans attendre 12 heures.
    En production, l'agent se déclenche seul toutes les 12 heures.
    """
    if not news_agent:
        raise HTTPException(status_code=503, detail="NewsAgent non initialisé")
    try:
        result = await news_agent.run()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur agent: {str(e)}")


@app.get("/news-agent/status")
async def news_agent_status():
    """Retourne l'état de l'agent et du scheduler"""
    next_run = None
    if scheduler and scheduler.running:
        job = scheduler.get_job("news_agent_job")
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "agent_ready": news_agent is not None,
        "scheduler_running": scheduler.running if scheduler else False,
        "interval": "toutes les 12 heures",
        "next_run": next_run,
    }


# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 15 — Agents avec mémoire
# ══════════════════════════════════════════════════════════════════


@app.post("/memory-agent/chat", response_model=MemoryChatResponse)
async def memory_chat(request: MemoryChatRequest):
    """
    Chat avec mémoire court terme.
    Envoie session_id=null pour démarrer une nouvelle session.
    Réutilise le même session_id pour continuer une conversation.
    """
    if not memory_agent:
        raise HTTPException(status_code=503, detail="MemoryAgent non initialisé")

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Le message ne peut pas être vide")

    try:
        response = await memory_agent.chat(
            message=request.message,
            session_id=request.session_id,
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur agent: {str(e)}")


@app.delete("/memory-agent/sessions/{session_id}")
async def delete_session(session_id: str):
    """Supprime une session de conversation"""
    success = clear_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session introuvable")
    return {"message": f"Session {session_id} supprimée"}


# A AJOUTER dans main.py si absent


@app.get("/memory-agent/sessions")
async def list_all_sessions():
    """
    Retourne toutes les sessions actives avec leurs informations.
    Format attendu par le frontend :
    {
        "active_sessions": 3,
        "sessions": [
            {
                "session_id": "abc123",
                "created_at": "2025-01-15T18:30:00",
                "total_turns": 4
            }
        ]
    }
    """
    session_ids = list_sessions()
    sessions_data = []

    for session_id in session_ids:
        session = get_session(session_id)
        if session:
            sessions_data.append(
                {
                    "session_id": session.session_id,
                    "created_at": session.created_at,
                    "total_turns": session.total_turns,
                }
            )

    return {"active_sessions": len(sessions_data), "sessions": sessions_data}


@app.get("/memory-agent/sessions/{session_id}")
async def get_session_detail(session_id: str):
    """Retourne l'historique d'une session spécifique"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "created_at": session.created_at,
        "total_turns": session.total_turns,
        "history": [
            {"role": turn.role, "content": turn.content} for turn in session.turns
        ],
    }


@app.get("/memory-agent/long-term", response_model=List[MemoryEntry])
async def get_long_term(category: str = None, limit: int = 10):
    """
    Consulte la mémoire long terme.
    Paramètre category : filtre par catégorie (tendance, rapport_news, fait_important)
    """
    entries = get_long_term_memory(category=category, limit=limit)
    return entries


@app.post("/memory-agent/long-term")
async def add_to_long_term(
    category: str, content: str, source: str = None, importance: int = 1
):
    """Ajoute manuellement une entrée en mémoire long terme"""
    entry = save_to_long_term(
        category=category,
        content=content,
        source=source,
        importance=importance,
    )
    return {"message": "Entrée mémorisée", "entry": entry}


@app.get("/memory-agent/status")
async def memory_agent_status():
    """Retourne l'état du MemoryAgent et des mémoires"""
    import os

    long_term_count = 0
    if os.path.exists("memory_store.json"):
        entries = get_long_term_memory(limit=1000)
        long_term_count = len(entries)

    return {
        "agent_ready": memory_agent is not None,
        "short_term_sessions": len(list_sessions()),
        "long_term_entries": long_term_count,
        "memory_file": "memory_store.json",
    }


# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 17 — Agent LangChain
# ══════════════════════════════════════════════════════════════════


@app.post("/lc-agent/analyze", response_model=AgentResponse)
async def lc_agent_analyze(request: AgentRequest):
    """
    Même analyse que /agent/analyze — mais avec LangChain.
    Comparer les deux réponses : elles doivent être identiques.
    """
    if not lc_agent:
        raise HTTPException(status_code=503, detail="LCAgent non initialisé")
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")
    try:
        response = await lc_agent.run(request.text, request.task)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur LCAgent: {str(e)}")


@app.get("/lc-agent/status")
async def lc_agent_status():
    return {
        "ready": lc_agent is not None,
        "framework": "LangChain",
        "model": "Gemini 2.5 Flash",
        "chains": ["sentiment", "themes", "complexite", "synthese"],
    }
