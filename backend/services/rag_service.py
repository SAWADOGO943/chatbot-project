import os
from pathlib import Path
from google import genai

# Dossier contenant les documents à indexer
DOCUMENTS_DIR = Path(__file__).parent.parent / "DOCUMENTS"


class RAGService:
    """
    Lit les documents, les stocke en mémoire, recherche par mots-clés,
    génère la réponse avec le nouveau Client Gemini (v1.0).
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY ou GEMINI_API_KEY manquante dans .env")

        # NOUVEAU : Initialisation via le Client
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.5-flash"
        self.documents = []  # Stockage en mémoire des chunks de texte

        if DOCUMENTS_DIR.exists():
            self._load_documents()

    def _load_documents(self):
        """Charge tous les fichiers .txt du dossier DOCUMENTS en mémoire"""
        self.documents = []
        for txt_path in DOCUMENTS_DIR.glob("*.txt"):
            try:
                text = txt_path.read_text(encoding="utf-8")
                chunks = self._split_text(text, chunk_size=1000, overlap=200)
                for chunk in chunks:
                    self.documents.append(
                        {
                            "content": chunk,
                            "source": txt_path.name,
                        }
                    )
                print(f"Chargé : {txt_path.name} ({len(chunks)} chunks)")
            except Exception as e:
                print(f"Erreur lecture {txt_path.name}: {e}")
        print(f"Total : {len(self.documents)} chunks en mémoire")

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> list:
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def _search(self, question: str, top_k: int = 4) -> list:
        question_words = set(question.lower().split())
        scored = []
        for doc in self.documents:
            content_words = set(doc["content"].lower().split())
            score = len(question_words & content_words)
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def index_documents(self) -> dict:
        if not DOCUMENTS_DIR.exists():
            return {
                "success": False,
                "message": f"Dossier DOCUMENTS introuvable",
                "documents_indexed": 0,
            }
        self._load_documents()
        return {
            "success": True,
            "message": f"Indexation OK : {len(self.documents)} chunks",
            "documents_indexed": len(self.documents),
        }

    async def query(self, question: str) -> dict:
        if not self.documents:
            raise Exception("Aucun document indexé. Appelez d'abord POST /rag/index")

        relevant_chunks = self._search(question)
        context = (
            "\n\n---\n\n".join(
                [f"Source : {d['source']}\n{d['content']}" for d in relevant_chunks]
            )
            if relevant_chunks
            else "Aucun passage pertinent trouvé."
        )

        # NOUVEAU : Appel via self.client.models.generate_content
        prompt = f"""Tu es un assistant expert. Réponds UNIQUEMENT via les extraits fournis.
        Extraits : {context}
        Question : {question}"""

        response = self.client.models.generate_content(
            model=self.model_id, contents=prompt
        )

        sources = [
            {"content": doc["content"][:300] + "...", "source": doc["source"]}
            for doc in relevant_chunks
        ]

        return {
            "answer": response.text.strip(),
            "sources": sources,
            "chunks_used": len(relevant_chunks),
        }

    def is_ready(self) -> bool:
        return len(self.documents) > 0
