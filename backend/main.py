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
        trigger=IntervalTrigger(minutes=5),
        id="news_agent_job",
        name="Veille tech automatique",
        replace_existing=True,
    )

    scheduler.start()
    print("Scheduler démarré — Agent autonome actif toutes les 5 minutes")

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


@app.get("/")  # Définit une route GET sur la racine de l'API
async def root():  # Fonction asynchrone pour vérifier l'état de santé du système
    return {  # Retourne un dictionnaire converti automatiquement en JSON
        "status": "ok",  # Confirme que le serveur est en ligne
        "message": "Chatbot API v3 is running",  # Version actuelle de l'application
        "rag_ready": rag_service.is_ready() if rag_service else False,  # Vérifie si la base de documents est prête
        "scheduler_running": scheduler.running if scheduler else False,  # Indique si les tâches automatiques sont actives
    }


@app.post("/chat", response_model=ChatResponse)  # Route POST pour le chat simple avec validation de sortie
async def chat(request: ChatRequest):  # Reçoit un objet ChatRequest validé par Pydantic
    if not request.message.strip():  # Vérifie si le message est vide ou ne contient que des espaces
        raise HTTPException(status_code=400, detail="Le message ne peut pas être vide")  # Erreur 400 (Bad Request)
    try:
        gemini_reply = await call_gemini(request.message)  # Appelle l'IA Gemini de manière asynchrone
        return ChatResponse(reply=gemini_reply)  # Retourne la réponse encapsulée dans le modèle ChatResponse
    except Exception as e:  # Capture toute erreur durant l'appel à l'IA
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")  # Erreur 500 (Internal Server Error)


@app.post("/rag/index", response_model=IndexResponse)  # Route POST pour lancer l'indexation documentaire
async def index_documents():  # Fonction pour transformer les fichiers en vecteurs mathématiques
    if not rag_service:  # Vérifie si le service RAG a été correctement initialisé
        raise HTTPException(status_code=503, detail="RAGService non initialisé")  # Erreur 503 (Service Unavailable)
    try:
        result = rag_service.index_documents()  # Lance la logique de lecture et de vectorisation des fichiers
        return IndexResponse(**result)  # Renvoie les stats (ex: nb de docs) en dépaquetant le dictionnaire
    except Exception as e:  # Capture les erreurs de lecture de fichiers ou d'API d'embedding
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation: {str(e)}")


@app.post("/rag/query")  # Route POST pour interroger l'IA avec le contexte de tes documents
async def rag_query(request: RAGRequest):  # Reçoit une question spécifique via l'objet RAGRequest
    if not rag_service:  # Vérifie l'existence du service de recherche sémantique
        raise HTTPException(status_code=503, detail="RAGService non initialisé")
    if not rag_service.is_ready():  # Vérifie qu'il existe un index (des documents chargés) en mémoire
        raise HTTPException(status_code=400, detail="Aucun document indexé")  # Bloque si la base est vide
    if not request.question.strip():  # Validation de sécurité pour éviter les questions vides
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide")
    try:
        response = await rag_service.query(request.question)  # Recherche les passages pertinents puis interroge l'IA
        return response  # Renvoie la réponse finale enrichie par tes propres documents
    except Exception as e:  # Gère les échecs de recherche sémantique ou de génération
        raise HTTPException(status_code=500, detail=f"Erreur RAG: {str(e)}")


@app.get("/rag/status")  # Route GET pour consulter l'état actuel de la base documentaire
async def rag_status():  # Fonction de monitoring pour le service RAG
    if not rag_service:  # Cas où le service n'est pas configuré dans le code
        return {"ready": False, "message": "Service non initialisé"}
    return {
        "ready": rag_service.is_ready(),  # Booléen indiquant si des documents sont exploitables
        "message": "Documents indexés et prêts"  # Message de succès si prêt
        if rag_service.is_ready()  # Condition ternaire Python pour le choix du message
        else "Aucun document indexé — utilisez POST /rag/index",  # Message d'aide si l'index est vide
    }
    


# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 13 — Agent d'analyse de texte
# ══════════════════════════════════════════════════════════════════


@app.post("/agent/analyze", response_model=AgentResponse)  # Route POST qui valide la sortie selon le schéma AgentResponse
async def agent_analyze(request: AgentRequest):  # Fonction asynchrone recevant le texte et la tâche à accomplir
    if not text_agent:  # Vérifie si l'instance de l'agent de texte a bien été créée au démarrage
        raise HTTPException(status_code=503, detail="Agent non initialisé")  # Erreur 503 si le service est indisponible
    if not request.text.strip():  # Sécurité : vérifie que le texte n'est pas vide ou rempli d'espaces
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")  # Erreur 400 (Bad Request)
    if len(request.text) > 5000:  # Limite la charge de travail pour éviter de saturer l'API Gemini ou la mémoire
        raise HTTPException(
            status_code=400, detail="Texte trop long. Maximum 5000 caractères."
        )  # Erreur 400 si le texte dépasse la limite autorisée
    try:
        # Exécute la logique de l'agent (analyse, sentiment, thèmes) de manière asynchrone
        response = await text_agent.run(request.text, request.task)
        return response  # Renvoie les résultats de l'analyse (formatés par le modèle de réponse)
    except Exception as e:  # Capture toute erreur imprévue lors de l'exécution de l'agent
        raise HTTPException(status_code=500, detail=f"Erreur agent: {str(e)}")  # Erreur 500 en cas de crash interne


@app.get("/agent/status")  # Route GET pour surveiller l'état de l'agent
async def agent_status():  # Fonction de diagnostic simple
    return {
        "ready": text_agent is not None,  # Booléen indiquant si l'agent est chargé en mémoire
        "agent": "TextAnalysisAgent",  # Identifiant du type d'agent utilisé
        "tools_available": [  # Liste les fonctionnalités "cerveau" disponibles pour cet agent
            "analyser_sentiment",  # Capacité à détecter l'émotion du texte
            "extraire_themes",     # Capacité à identifier les sujets principaux
            "evaluer_complexite", # Capacité à juger le niveau de langue ou de difficulté
        ],
    }

# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 14 — Agent autonome de veille tech
# ══════════════════════════════════════════════════════════════════


@app.post("/news-agent/run", response_model=AgentRunResult)  # Route POST pour déclencher l'agent, valide la sortie via AgentRunResult
async def news_agent_run():  # Fonction asynchrone pour lancer manuellement la veille technologique
    """
    Déclenche l'agent manuellement.
    Utile pour tester sans attendre 12 heures.
    """
    if not news_agent:  # Vérifie si l'instance NewsScraperAgent est bien initialisée en mémoire
        raise HTTPException(status_code=503, detail="NewsAgent non initialisé")  # Erreur 503 si le service est manquant
    try:
        result = await news_agent.run()  # Exécute la boucle complète (Scraping -> Analyse -> Email)
        return result  # Renvoie le rapport final et le statut de l'envoi
    except Exception as e:  # Capture toute erreur (échec scraping, erreur Gemini, etc.)
        raise HTTPException(status_code=500, detail=f"Erreur agent: {str(e)}")  # Erreur 500 avec le détail technique


@app.get("/news-agent/status")  # Route GET pour consulter l'état de santé de l'automatisation
async def news_agent_status():  # Fonction de diagnostic pour l'agent et son planificateur (scheduler)
    """Retourne l'état de l'agent et du scheduler"""
    next_run = None  # Initialisation de la variable pour la date du prochain passage
    if scheduler and scheduler.running:  # Vérifie si le gestionnaire de tâches (APScheduler) est actif
        job = scheduler.get_job("news_agent_job")  # Récupère la tâche spécifique nommée "news_agent_job"
        if job and job.next_run_time:  # Si la tâche existe et qu'elle a une heure de prévue
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")  # Formate la date en texte lisible (Année-Mois-Jour Heure)

    return {  # Retourne les informations de monitoring
        "agent_ready": news_agent is not None,  # Confirme que l'agent est prêt à être utilisé
        "scheduler_running": scheduler.running if scheduler else False,  # Indique si le mode automatique est ON
        "interval": "toutes les 12 heures",  # Rappel du paramétrage de la fréquence
        "next_run": next_run,  # Affiche l'heure exacte du prochain scan automatique
    }