import os
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
rag_service = None
text_agent = None
news_agent = None
scheduler = None


# ── LIFESPAN (Gestion propre du démarrage et de l'arrêt) ──────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service, text_agent, news_agent, scheduler

    print("🚀 Démarrage du serveur...")

    # Initialisation des services
    rag_service = RAGService()
    text_agent = TextAnalysisAgent()
    news_agent = NewsScraperAgent()

    # Démarrage du scheduler
    scheduler = AsyncIOScheduler()

    # Planification : Correction ICI -> On passe la fonction sans l'appeler
    # L'AsyncIOScheduler s'occupe de l'await automatiquement
    scheduler.add_job(
        func=news_agent.run,
        trigger=IntervalTrigger(minutes=5),
        id="news_agent_job",
        name="Veille tech automatique",
        replace_existing=True,
    )

    scheduler.start()
    print("⏰ Scheduler démarré — Agent actif toutes les 12 heures")

    yield  # L'application tourne ici

    # Arrêt propre
    if scheduler:
        scheduler.shutdown()
        print("🛑 Scheduler arrêté")


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

# ── ROUTES ─────────────────────────────────────────────────────────


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
        # Assure-toi que cette méthode est synchrone ou ajoute 'await' si elle est async
        result = rag_service.index_documents()
        return IndexResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation: {str(e)}")


@app.post("/rag/query")
async def rag_query(request: RAGRequest):
    if not rag_service or not rag_service.is_ready():
        raise HTTPException(
            status_code=400, detail="RAG non prêt ou aucun document indexé"
        )
    try:
        response = await rag_service.query(request.question)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur RAG: {str(e)}")


@app.post("/agent/analyze", response_model=AgentResponse)
async def agent_analyze(request: AgentRequest):
    if not text_agent:
        raise HTTPException(status_code=503, detail="Agent non initialisé")
    try:
        response = await text_agent.run(request.text, request.task)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur agent: {str(e)}")


@app.post("/news-agent/run", response_model=AgentRunResult)
async def news_agent_run():
    if not news_agent:
        raise HTTPException(status_code=503, detail="NewsAgent non initialisé")
    try:
        return await news_agent.run()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur agent: {str(e)}")


@app.get("/news-agent/status")
async def news_agent_status():
    next_run = None
    if scheduler and scheduler.running:
        job = scheduler.get_job("news_agent_job")
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "agent_ready": news_agent is not None,
        "scheduler_running": scheduler.running if scheduler else False,
        "next_run": next_run,
    }


# IMPORTANT : Ne pas mettre uvicorn.run() ici pour un déploiement Render.
# Utilise la "Start Command" sur Render :
# uvicorn main:app --host 0.0.0.0 --port $PORT
