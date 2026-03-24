# Permet de gérer les événements de démarrage et d'arrêt (cycle de vie) de l'application
from contextlib import asynccontextmanager

# FastAPI est le framework web ; HTTPException permet de renvoyer des erreurs propres (ex: 404, 500)
from fastapi import FastAPI, HTTPException

# Middleware indispensable pour autoriser votre frontend à communiquer avec ce backend
from fastapi.middleware.cors import CORSMiddleware

# Charge les variables d'environnement définies dans votre fichier .env (ex: GOOGLE_API_KEY)
from dotenv import load_dotenv

# Importe les modèles Pydantic pour valider la structure des données de chat (texte envoyé/reçu)
from schemas.chat_schema import ChatRequest, ChatResponse

# Importe les modèles pour le RAG (requêtes sur documents, réponses et statut d'indexation)
from schemas.rag_schema import RAGRequest, RAGResponse, IndexResponse

# Importe la fonction qui appelle directement le modèle Gemini pour une discussion simple
from services.gemini_service import call_gemini

# Importe votre service RAG qui gère la base de données ChromaDB et l'indexation de vos PDF
from services.rag_service import RAGService


# Charge .env AVANT tout code qui utilise os.getenv()
load_dotenv()

# ── SINGLETON RAGService ───────────────────────────────────────────
# Variable globale : une seule instance partagée par toutes les requêtes
rag_service: RAGService = None


# ── LIFESPAN : Actions au démarrage/arrêt de FastAPI ──────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Exécuté au démarrage du serveur.
    Initialise le RAGService une seule fois.
    """
    global rag_service
    print("🚀 Démarrage du serveur...")
    rag_service = RAGService()
    if rag_service.is_ready():
        print("✅ RAGService prêt avec des documents déjà indexés")
    else:
        print("ℹ️  RAGService prêt — en attente d'indexation")
    yield  # ← L'application tourne ici
    print("🛑 Arrêt du serveur")


# ── APPLICATION FASTAPI ────────────────────────────────────────────
app = FastAPI(
    title="Chatbot IA + RAG API",
    description="Backend d'un chatbot fullstack avec mémoire documentaire",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── ROUTE DE SANTÉ ─────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Chatbot API v2 is running 🚀",
        "rag_ready": rag_service.is_ready() if rag_service else False,
    }


# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 1 — Chatbot simple (inchangées)
# ══════════════════════════════════════════════════════════════════


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chatbot simple Semaine 1 — Gemini sans contexte documentaire"""

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Le message ne peut pas être vide")

    try:
        gemini_reply = await call_gemini(request.message)
        return ChatResponse(reply=gemini_reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


# ══════════════════════════════════════════════════════════════════
# ROUTES SEMAINE 2 — RAG
# ══════════════════════════════════════════════════════════════════


@app.post("/rag/index", response_model=IndexResponse)
async def index_documents():
    """
    Indexe tous les documents du dossier /documents.
    À appeler après avoir ajouté/modifié des fichiers.
    """

    if not rag_service:
        raise HTTPException(status_code=503, detail="RAGService non initialisé")

    try:
        result = rag_service.index_documents()
        return IndexResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation: {str(e)}")


@app.post("/rag/query", response_model=RAGResponse)
async def rag_query(request: RAGRequest):
    """
    Pose une question au RAG.
    Cherche dans les documents indexés et génère une réponse sourcée.
    """

    if not rag_service:
        raise HTTPException(status_code=503, detail="RAGService non initialisé")

    if not rag_service.is_ready():
        raise HTTPException(
            status_code=400,
            detail="Aucun document indexé. Appelez d'abord POST /rag/index",
        )

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide")

    try:
        response = await rag_service.query(request.question)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur RAG: {str(e)}")


@app.get("/rag/status")
async def rag_status():
    """Vérifie si des documents sont indexés et prêts"""

    if not rag_service:
        return {"ready": False, "message": "Service non initialisé"}

    return {
        "ready": rag_service.is_ready(),
        "message": "Documents indexés et prêts"
        if rag_service.is_ready()
        else "Aucun document indexé — utilisez POST /rag/index",
    }
