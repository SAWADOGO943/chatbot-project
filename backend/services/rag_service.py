# Importation des modules standards pour la gestion des chemins et variables d'environnement
import os
from pathlib import Path

# ── IMPORTS LANGCHAIN (modules communautaires et officiels) ────────
# Chargeurs de documents pour différents formats
from langchain_community.document_loaders import (
    PyPDFLoader,  # Chargeur spécifique pour les fichiers PDF
    TextLoader,  # Chargeur pour les fichiers texte simples
)

# Outil de découpage intelligent des documents en morceaux (chunks)
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Modèle d'embeddings Google (transforme texte → vecteurs)
from langchain_huggingface import HuggingFaceEmbeddings

# Base de données vectorielle locale persistante (Chroma)
from langchain_chroma import Chroma

# Modèle de langage conversationnel Gemini
from langchain_google_genai import ChatGoogleGenerativeAI

# ── Imports pour le style LCEL moderne (chaînes de récupération) ────
# Note : ces imports viennent de langchain-classic car langchain a splitté ses modules legacy
from langchain_classic.chains import (
    create_retrieval_chain,
)  # Crée la chaîne complète retrieval + génération
from langchain_classic.chains.combine_documents import (
    create_stuff_documents_chain,
)  # Combine plusieurs docs dans un prompt

# Type de prompt adapté aux modèles de chat (Gemini)
from langchain_core.prompts import ChatPromptTemplate

# Nos schémas Pydantic pour typer les réponses
from schemas.rag_schema import RAGResponse, SourceChunk

# ── CONFIGURATION GLOBALE ──────────────────────────────────────────
# Chemin vers le dossier contenant les documents à indexer
# ── CONFIGURATION ──────────────────────────────────────────────────

# Assurez-vous que le nom est EXACTEMENT le même que dans VS Code
DOCUMENTS_DIR = Path(__file__).parent.parent / "DOCUMENTS"

# Dossier où ChromaDB stockera sa base (il se créera tout seul)
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


class RAGService:
    """
    Service RAG complet :
    - indexation des documents
    - récupération des passages pertinents
    - génération de réponse avec Gemini
    Version compatible LangChain 2025+ (style LCEL)
    """

    def __init__(self):
        # Récupération de la clé API depuis les variables d'environnement
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            # Sécurité : on arrête tout si la clé manque
            raise ValueError("GOOGLE_API_KEY manquante dans .env")

        # Initialisation du modèle d'embeddings (Google text-embedding-004)
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        # Initialisation du LLM Gemini Flash (rapide et économique)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",  # Version rapide de Gemini
            google_api_key=api_key,
            temperature=0.3,  # Faible température → réponses plus déterministes
        )

        # Tentative de chargement d'une base Chroma existante
        self.vectorstore = self._load_existing_vectorstore()

        # La chaîne LCEL sera créée plus tard (lazy initialization)
        self.chain = None

    def _load_existing_vectorstore(self):
        """Charge une base Chroma déjà existante si elle est présente et non vide"""
        # Vérifie si le dossier existe ET contient au moins un fichier
        if CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir()):
            print("✅ Vectorstore existant chargé depuis le disque")
            return Chroma(
                persist_directory=str(CHROMA_DIR),  # Où sont stockées les données
                embedding_function=self.embeddings,  # Même embedding que pour l'indexation
            )
        # Sinon on signale qu'il faudra indexer
        print("ℹ️ Aucun vectorstore existant — indexation nécessaire")
        return None

    def index_documents(self) -> dict:
        """Pipeline complet d'indexation : chargement → split → embedding → stockage"""
        # Vérification de l'existence du dossier documents
        if not DOCUMENTS_DIR.exists():
            return {
                "success": False,
                "message": f"Dossier documents introuvable : {DOCUMENTS_DIR}",
                "documents_indexed": 0,
            }

        documents = []  # Liste qui va contenir tous les documents chargés

        # ── Chargement des PDF ────────────────────────────────
        for pdf_path in DOCUMENTS_DIR.glob("*.pdf"):
            try:
                loader = PyPDFLoader(str(pdf_path))  # Crée un chargeur PDF
                docs = loader.load()  # Charge toutes les pages
                documents.extend(docs)  # Ajoute à la liste globale
                print(f" 📄 PDF chargé : {pdf_path.name} ({len(docs)} pages)")
            except Exception as e:
                print(f" ⚠️ Erreur PDF {pdf_path.name}: {e}")

        # ── Chargement des fichiers texte ─────────────────────
        for txt_path in DOCUMENTS_DIR.glob("*.txt"):
            try:
                loader = TextLoader(str(txt_path), encoding="utf-8")
                docs = loader.load()
                documents.extend(docs)
                print(f" 📄 TXT chargé : {txt_path.name}")
            except Exception as e:
                print(f" ⚠️ Erreur TXT {txt_path.name}: {e}")

        # Sécurité : aucun document → on arrête
        if not documents:
            return {
                "success": False,
                "message": "Aucun document trouvé. Ajoutez des .pdf ou .txt",
                "documents_indexed": 0,
            }

        # ── Découpage en chunks ───────────────────────────────
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Taille maximale d'un chunk (caractères)
            chunk_overlap=200,  # Chevauchement pour ne pas couper les phrases
            length_function=len,  # Fonction pour mesurer la longueur
            separators=["\n\n", "\n", ".", " ", ""],  # Hiérarchie de coupure
        )
        chunks = splitter.split_documents(documents)
        print(f"\n ✂️ {len(documents)} docs → {len(chunks)} chunks")

        # ── Création des embeddings + stockage dans Chroma ────
        print(" 🔢 Création embeddings...")
        self.vectorstore = Chroma.from_documents(
            documents=chunks,  # Les morceaux de texte
            embedding=self.embeddings,  # Modèle d'embedding
            persist_directory=str(CHROMA_DIR),  # Où sauvegarder sur disque
        )
        print(f" 💾 Vectorstore sauvegardé dans {CHROMA_DIR}")

        # La chaîne doit être recréée car le vectorstore a changé
        self._build_chain()

        return {
            "success": True,
            "message": f"Indexation OK : {len(chunks)} chunks créés",
            "documents_indexed": len(chunks),
        }

    def _build_chain(self):
        """Construit la chaîne de traitement RAG (LCEL style)"""
        if not self.vectorstore:
            return  # Impossible sans vectorstore

        # Template du prompt donné au LLM
        prompt_template = """Tu es un assistant expert qui répond aux questions
en te basant UNIQUEMENT sur les extraits de documents fournis ci-dessous.
Si la réponse ne se trouve pas dans les extraits, dis clairement :
"Je ne trouve pas cette information dans les documents disponibles."
Ne fais pas de suppositions ni d'inventions.

Extraits pertinents :
{context}

Question : {input}

Réponse (en français, claire, structurée) :"""

        prompt = ChatPromptTemplate.from_template(prompt_template)

        # Partie qui "fourre" tous les documents dans le prompt
        question_answer_chain = create_stuff_documents_chain(
            llm=self.llm, prompt=prompt
        )

        # Chaîne complète : recherche → combinaison → génération
        self.chain = create_retrieval_chain(
            retriever=self.vectorstore.as_retriever(
                search_kwargs={"k": 4}
            ),  # Top 4 chunks
            combine_docs_chain=question_answer_chain,
        )

    async def query(self, question: str) -> RAGResponse:
        """Exécute une question RAG de façon asynchrone"""
        if not self.vectorstore:
            raise Exception("Aucun document indexé. Appelez d'abord /rag/index")

        if not self.chain:
            self._build_chain()  # Sécurité : on crée la chaîne si besoin

        # Exécution asynchrone de la chaîne
        result = await self.chain.ainvoke({"input": question})

        # Extraction des éléments de la réponse
        answer = result["answer"]  # La réponse générée
        source_docs = result.get("context", [])  # Les documents retrouvés

        sources = []
        for doc in source_docs:
            source_name = doc.metadata.get("source", "Inconnu")  # Chemin du fichier
            page = doc.metadata.get("page")  # Numéro de page (PDF)

            # Aperçu du contenu (tronqué à 300 caractères)
            content_preview = (
                doc.page_content[:300] + "..."
                if len(doc.page_content) > 300
                else doc.page_content
            )

            sources.append(
                SourceChunk(
                    content=content_preview,
                    source=Path(source_name).name,  # Seulement le nom du fichier
                    page=page + 1 if page is not None else None,  # Pages commencent à 1
                )
            )

        # Retour formaté selon le schéma Pydantic
        return RAGResponse(
            answer=answer,
            sources=sources,
            chunks_used=len(source_docs),
        )

    def is_ready(self) -> bool:
        """Indicateur simple : le service est-il prêt à répondre ?"""
        return self.vectorstore is not None
