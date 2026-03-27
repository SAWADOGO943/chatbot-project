from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from schemas.chat_schema import ChatRequest, ChatResponse
from schemas.rag_schema import RAGRequest, RAGResponse, IndexResponse
from services.gemini_service import call_gemini
from services.rag_service import RAGService

load_dotenv()

rag_service: RAGService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service
    print("Démarrage du serveur...")
    rag_service = RAGService()
    if rag_service.is_ready():
        print("RAGService prêt avec des documents déjà indexés")
    else:
        print("RAGService prêt — en attente d'indexation")
    yield
    print("Arrêt du serveur")


app = FastAPI(
    title="Chatbot IA + RAG API",
    description="Backend d'un chatbot fullstack avec mémoire documentaire",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Chatbot API v2 is running",
        "rag_ready": rag_service.is_ready() if rag_service else False,
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
    if not rag_service:
        return {"ready": False, "message": "Service non initialisé"}
    return {
        "ready": rag_service.is_ready(),
        "message": "Documents indexés et prêts"
        if rag_service.is_ready()
        else "Aucun document indexé — utilisez POST /rag/index",
    }
