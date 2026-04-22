from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Schemas
from schemas.chat_schema import ChatRequest, ChatResponse
from schemas.rag_schema import RAGRequest, RAGResponse, IndexResponse
from schemas.agent_schema import AgentRequest, AgentResponse

# Services et agents
from services.gemini_service import call_gemini
from services.rag_service import RAGService
from agents.text_analysis_agent import TextAnalysisAgent
from agents.news_scraper_agent import NewsScraperAgent

# Chargement des variables d'environnement
load_dotenv()

# ── VARIABLES GLOBALES ─────────────────────────────────────────────
rag_service = None
text_agent = None
news_agent = None
scheduler = None


# ── LIFESPAN ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service, text_agent, news_agent, scheduler
    print("🚀 Démarrage du serveur...")

    try:
        # Initialisation unique des services
        rag_service = RAGService()
        text_agent = TextAnalysisAgent()
        news_agent = NewsScraperAgent()

        # Démarrage du scheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            func=news_agent.run,
            trigger=IntervalTrigger(minutes=5),
            id="news_agent_job",
            name="Veille tech automatique",
            replace_existing=True,
        )
        scheduler.start()
        print("⏰ Scheduler démarré")

    except Exception as e:
        print(f"⚠️ Erreur lors de l'initialisation : {e}")

    yield

    if scheduler:
        scheduler.shutdown()
        print("🛑 Scheduler arrêté")


# ── APPLICATION ────────────────────────────────────────────────────
app = FastAPI(
    title="Chatbot IA + RAG + Agents API",
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
        "rag_ready": rag_service.is_ready() if rag_service else False,
        "scheduler_running": scheduler.running if scheduler else False,
    }


@app.api_route("/news-agent/run", methods=["GET", "POST"])
async def news_agent_run_route(background_tasks: BackgroundTasks):
    """
    Route pour UptimeRobot : répond vite et travaille en arrière-plan.
    """
    if not news_agent:
        raise HTTPException(status_code=503, detail="Agent non initialisé")

    background_tasks.add_task(news_agent.run)

    next_run = None
    if scheduler and scheduler.running:
        job = scheduler.get_job("news_agent_job")
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "status": "success",
        "message": "Scraper lancé en tâche de fond",
        "next_scheduled_run": next_run,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message vide")
    try:
        reply = await call_gemini(request.message)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/index", response_model=IndexResponse)
async def index_documents():
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG non prêt")
    try:
        result = rag_service.index_documents()
        return IndexResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/query")
async def rag_query(request: RAGRequest):
    if not rag_service or not rag_service.is_ready():
        raise HTTPException(status_code=400, detail="RAG non indexé")
    try:
        return await rag_service.query(request.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/analyze", response_model=AgentResponse)
async def agent_analyze(request: AgentRequest):
    if not text_agent:
        raise HTTPException(status_code=503, detail="Agent non prêt")
    try:
        return await text_agent.run(request.text, request.task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
