import os
from pathlib import Path
import google.generativeai as genai

# Dossier contenant les documents à indexer
DOCUMENTS_DIR = Path(__file__).parent.parent / "DOCUMENTS"


class RAGService:
    """
    Lit les documents, les stocke en mémoire, recherche par mots-clés,
    génère la réponse avec Gemini directement.
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY ou GEMINI_API_KEY manquante dans .env")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.documents = []  # Stockage en mémoire des chunks de texte

        # Chargement automatique si des documents existent
        if DOCUMENTS_DIR.exists():
            self._load_documents()

    def _load_documents(self):
        """Charge tous les fichiers .txt du dossier DOCUMENTS en mémoire"""
        self.documents = []

        for txt_path in DOCUMENTS_DIR.glob("*.txt"):
            try:
                text = txt_path.read_text(encoding="utf-8")
                # Découpage en chunks de 1000 caractères avec chevauchement de 200
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
        """Découpe un texte en morceaux avec chevauchement"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def _search(self, question: str, top_k: int = 4) -> list:
        """
        Recherche simple par mots-clés.
        Retourne les chunks contenant le plus de mots de la question.
        """
        question_words = set(question.lower().split())

        scored = []
        for doc in self.documents:
            content_words = set(doc["content"].lower().split())
            score = len(question_words & content_words)  # Mots en commun
            if score > 0:
                scored.append((score, doc))

        # Tri par score décroissant, on prend les top_k meilleurs
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def index_documents(self) -> dict:
        """Recharge les documents depuis le disque"""
        if not DOCUMENTS_DIR.exists():
            return {
                "success": False,
                "message": f"Dossier DOCUMENTS introuvable : {DOCUMENTS_DIR}",
                "documents_indexed": 0,
            }

        self._load_documents()

        return {
            "success": True,
            "message": f"Indexation OK : {len(self.documents)} chunks chargés",
            "documents_indexed": len(self.documents),
        }

    async def query(self, question: str) -> dict:
        """
        Recherche les passages pertinents puis génère une réponse avec Gemini.
        """
        if not self.documents:
            raise Exception("Aucun document indexé. Appelez d'abord POST /rag/index")

        # Recherche des chunks pertinents
        relevant_chunks = self._search(question)

        if not relevant_chunks:
            context = "Aucun passage pertinent trouvé dans les documents."
        else:
            context = "\n\n---\n\n".join(
                [
                    f"Source : {doc['source']}\n{doc['content']}"
                    for doc in relevant_chunks
                ]
            )

        # Prompt envoyé à Gemini
        prompt = f"""Tu es un assistant expert qui répond aux questions
en te basant UNIQUEMENT sur les extraits de documents fournis ci-dessous.
Si la réponse ne se trouve pas dans les extraits, dis clairement :
"Je ne trouve pas cette information dans les documents disponibles."
Ne fais pas de suppositions ni d'inventions.

Extraits pertinents :
{context}

Question : {question}

Réponse (en français, claire, structurée) :"""

        response = self.model.generate_content(prompt)

        sources = [
            {
                "content": doc["content"][:300] + "..."
                if len(doc["content"]) > 300
                else doc["content"],
                "source": doc["source"],
                "page": None,
            }
            for doc in relevant_chunks
        ]

        return {
            "answer": response.text.strip(),
            "sources": sources,
            "chunks_used": len(relevant_chunks),
        }

    def is_ready(self) -> bool:
        """Retourne True si des documents sont chargés en mémoire"""
        return len(self.documents) > 0
