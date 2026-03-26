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

# Cet endpoint transforme vos documents (PDF, texte, etc.)
#  en "nombres" (embeddings) pour qu'ils soient exploitables par l'IA.


@app.post("/rag/index", response_model=IndexResponse)
async def index_documents():
    """
    Déclenche le scan du dossier /documents et crée la base de données vectorielle.
    """
    # Vérification de sécurité : s'assure que la classe RAGService a bien été instanciée au démarrage.
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAGService non initialisé")

    try:
        # Appel de la logique métier qui lit les fichiers et génère les vecteurs.
        result = rag_service.index_documents()
        # Retourne un objet validé par Pydantic (IndexResponse).
        return IndexResponse(**result)
    except Exception as e:
        # Capture toute erreur (fichier corrompu, échec API d'embedding) pour éviter un crash serveur.
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation: {str(e)}")


# 2. Endpoint de Requête (/rag/query)
# C'est ici que l'utilisateur pose une question.
# Le système cherche les passages pertinents dans les documents avant de générer une réponse.


@app.post("/rag/query", response_model=RAGResponse)
async def rag_query(request: RAGRequest):
    """
    Recherche la réponse dans les documents indexés.
    """
    # 1. Vérifie si le service existe.
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAGService non initialisé")

    # 2. Vérifie si des données ont été indexées (évite une recherche dans le vide).
    if not rag_service.is_ready():
        raise HTTPException(
            status_code=400,
            detail="Aucun document indexé. Appelez d'abord POST /rag/index",
        )

    # 3. Validation de l'entrée utilisateur pour éviter les requêtes inutiles.
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide")

    try:
        # Appel asynchrone pour interroger le LLM et la base vectorielle.
        response = await rag_service.query(request.question)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur RAG: {str(e)}")


# 3. Endpoint de Statut (/rag/status)
# Indispensable pour le frontend (votre portfolio ou interface React) afin de savoir
#  s'il faut afficher un bouton "Chercher" ou un avertissement.


@app.get("/rag/status")
async def rag_status():
    """
    Retourne l'état actuel de préparation du système RAG.
    """
    # Si le service n'est même pas configuré (clés API manquantes, etc.).
    if not rag_service:
        return {"ready": False, "message": "Service non initialisé"}

    # Vérifie dynamiquement si la base vectorielle contient des données.
    return {
        "ready": rag_service.is_ready(),
        "message": "Documents indexés et prêts"
        if rag_service.is_ready()
        else "Aucun document indexé — utilisez POST /rag/index",
    }
