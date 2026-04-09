from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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

load_dotenv()

# ── VARIABLES GLOBALES ─────────────────────────────────────────────
rag_service: RAGService = None
text_agent: TextAnalysisAgent = None
news_agent: NewsScraperAgent = None
scheduler: AsyncIOScheduler = None


# ── LIFESPAN ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service, text_agent, news_agent, scheduler

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

    news_agent = NewsScraperAgent()
    print("NewsScraperAgent prêt")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
