from pydantic import BaseModel
from typing import List, Optional


class NewsArticle(BaseModel):
    """Représente un article scrapé"""

    title: str  # Titre de l'article
    url: str  # URL source
    content: str  # Contenu extrait
    source: str  # Nom du site source


class NewsReport(BaseModel):
    """Le rapport complet généré par l'agent"""

    generated_at: str  # Date et heure de génération
    articles_found: int  # Nombre d'articles trouvés
    articles_analyzed: int  # Nombre d'articles analysés avec succès
    summary: str  # Résumé global généré par Gemini
    top_articles: List[NewsArticle]  # Les articles retenus
    key_trends: List[str]  # Les tendances clés identifiées


class AgentRunResult(BaseModel):
    """Résultat d'une exécution de l'agent"""

    success: bool
    message: str
    report: Optional[NewsReport] = None
    error: Optional[str] = None
