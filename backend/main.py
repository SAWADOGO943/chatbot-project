from contextlib import (
    asynccontextmanager,
)  # Pour gérer le cycle de vie de l'application (start/stop)
from fastapi import (
    FastAPI,
    HTTPException,
)  # Le framework web et la gestion des erreurs HTTP
from fastapi.middleware.cors import (
    CORSMiddleware,
)  # Pour autoriser les requêtes venant d'autres domaines (Frontend)
from dotenv import load_dotenv  # Pour charger les variables secrètes (.env)

# Importation des modèles de données (schemas) et des logiques métiers (services)
from schemas.chat_schema import ChatRequest, ChatResponse
from schemas.rag_schema import RAGRequest, IndexResponse
from services.gemini_service import call_gemini
from services.rag_service import RAGService

from agents.text_analysis_agent import TextAnalysisAgent
from schemas.agent_schema import AgentRequest, AgentResponse

load_dotenv()  # Initialise le chargement des variables d'environnement

# Déclaration globale du service RAG (sera instancié au démarrage)
rag_service: RAGService = None
text_agent: TextAnalysisAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service, text_agent

    print("Démarrage du serveur...")

    rag_service = RAGService()
    if rag_service.is_ready():
        print("RAGService prêt avec des documents déjà indexés")
    else:
        print("RAGService prêt — en attente d'indexation")

    text_agent = TextAnalysisAgent()
    print("TextAnalysisAgent prêt")

    yield
    print("Arrêt du serveur")


# Création de l'instance principale de l'API avec ses métadonnées
app = FastAPI(
    title="Chatbot IA + RAG API",
    description="Backend d'un chatbot fullstack avec mémoire documentaire",
    version="2.0.0",
    lifespan=lifespan,  # Lie le cycle de vie défini plus haut
)


# Configuration du CORS pour permettre au Frontend (Localhost ou Vercel) de communiquer avec l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",  # Live Server VS Code
        "http://127.0.0.1:5500",  # Adresse locale alternative
        "https://chatbot-project.vercel.app",  # URL de production
    ],
    allow_credentials=True,  # Autorise l'envoi de cookies/auth
    allow_methods=["*"],  # Autorise GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Autorise tous les headers (Content-Type, etc.)
)


@app.get("/")
async def root():
    """Point d'entrée de test pour vérifier que l'API répond"""
    return {
        "status": "ok",
        "message": "Chatbot API v2 is running",
        "rag_ready": rag_service.is_ready() if rag_service else False,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Endpoint pour une discussion simple avec l'IA sans contexte documentaire"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Le message ne peut pas être vide")
    try:
        # Appel du service Gemini créé précédemment
        gemini_reply = await call_gemini(request.message)
        return ChatResponse(reply=gemini_reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.post("/rag/index", response_model=IndexResponse)
async def index_documents():
    """Endpoint pour lire les fichiers locaux et les transformer en vecteurs mathématiques"""
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAGService non initialisé")
    try:
        # Déclenche l'indexation (embedding) des documents
        result = rag_service.index_documents()
        return IndexResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation: {str(e)}")


@app.post("/rag/query")
async def rag_query(request: RAGRequest):
    """Endpoint pour poser une question basée sur les documents indexés"""
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAGService non initialisé")
    # Sécurité : on ne peut pas requêter si la base de données est vide
    if not rag_service.is_ready():
        raise HTTPException(
            status_code=400,
            detail="Aucun document indexé. Appelez d'abord POST /rag/index",
        )
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide")
    try:
        # Recherche les morceaux de textes pertinents puis interroge l'IA
        response = await rag_service.query(request.question)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur RAG: {str(e)}")


@app.get("/rag/status")
async def rag_status():
    """Permet au Frontend de savoir si le bouton de chat 'RAG' doit être activé"""
    if not rag_service:
        return {"ready": False, "message": "Service non initialisé"}
    return {
        "ready": rag_service.is_ready(),
        "message": "Documents indexés et prêts"
        if rag_service.is_ready()
        else "Aucun document indexé — utilisez POST /rag/index",
    }


# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 13 — Agent IA
# ══════════════════════════════════════════════════════════════════


@app.post("/agent/analyze", response_model=AgentResponse)
async def agent_analyze(request: AgentRequest):
    """
    Lance l'agent d'analyse de texte.
    L'agent planifie, exécute et observe son propre travail.
    Le raisonnement complet est retourné dans la réponse.
    """
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
    """Vérifie si l'agent est prêt et liste ses outils"""
    return {
        "ready": text_agent is not None,
        "agent": "TextAnalysisAgent",
        "tools_available": [
            "analyser_sentiment",
            "extraire_themes",
            "evaluer_complexite",
        ],
    }
