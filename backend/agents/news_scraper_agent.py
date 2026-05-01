from datetime import datetime
from typing import List
import asyncio

from agents.base_agent import BaseAgent
from services.scraper_service import scrape_tech_news
from services.email_service import send_news_report
from schemas.news_schema import NewsReport, AgentRunResult


class NewsScraperAgent(BaseAgent):
    """
    Agent autonome de veille technologique.
    S'exécute automatiquement toutes les 12 heures.
    """

    def __init__(self):
        super().__init__()
        print("NewsScraperAgent initialisé et prêt")

    def analyser_articles(self, articles_content: str) -> dict:
    """
    Envoie tous les articles à Gemini pour analyse globale.
    Enrichit l'analyse avec la mémoire long terme des rapports précédents.
    """

    # Récupérer la mémoire long terme avant d'analyser
    from services.memory_service import get_memory_context
    memory_context = get_memory_context(category="tendance", limit=5)

    prompt = f"""Tu es un agent de veille technologique expert avec mémoire.
Tu viens de scraper plusieurs articles tech sur internet.
Avant d'analyser, consulte ce que tu as observé lors de tes analyses précédentes.

{memory_context}

ARTICLES SCRAPÉS AUJOURD'HUI :
{articles_content}

Produis ton analyse dans ce format EXACT — respecte les séparateurs :

RÉSUMÉ_GLOBAL:
[Un résumé en 4 à 6 phrases. Compare avec tes observations passées si pertinent.
Signale les nouvelles tendances et celles qui se confirment dans le temps.]

TENDANCES:
- [Tendance 1 — précise si c'est une confirmation ou une nouveauté]
- [Tendance 2]
- [Tendance 3]
- [Tendance 4 si présente]
- [Tendance 5 si présente]

ANALYSE:
[2 à 3 phrases sur ce que ces tendances signifient sur la durée, en tenant compte
de ce que tu as déjà observé dans tes rapports précédents.]"""

    response = self.model.generate_content(prompt)
    text = response.text.strip()

    # Parse identique à avant
    summary = ""
    if "RÉSUMÉ_GLOBAL:" in text:
        parts = text.split("RÉSUMÉ_GLOBAL:")
        if len(parts) > 1:
            summary_part = parts[1].split("TENDANCES:")[0].strip()
            summary = summary_part

    trends = []
    if "TENDANCES:" in text:
        parts = text.split("TENDANCES:")
        if len(parts) > 1:
            trends_part = parts[1].split("ANALYSE:")[0].strip()
            for line in trends_part.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    trend = line[1:].strip()
                    if trend:
                        trends.append(trend)

    if "ANALYSE:" in text:
        parts = text.split("ANALYSE:")
        if len(parts) > 1:
            analyse = parts[1].strip()
            summary = summary + "\n\n" + analyse if summary else analyse

    if not summary:
        summary = text[:1000]
    if not trends:
        trends = ["Analyse des tendances indisponible"]

    return {"summary": summary, "trends": trends}

async def run(self) -> AgentRunResult:
    """
    Boucle principale de l'agent autonome.
    Collecte → Analyse (avec mémoire) → Sauvegarde → Email.
    """
    print(f"\n{'='*60}")
    print(f"AGENT AUTONOME DÉMARRÉ")
    print(f"Heure : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    try:
        # ── ÉTAPE 1 : COLLECTE ET SCRAPING ──────────────────────────
        print("Etape 1 — Collecte et scraping des articles...")
        articles = await scrape_tech_news(max_articles=5)

        if not articles:
            print("Aucun article trouvé — abandon")
            return AgentRunResult(
                success=False,
                message="Aucun article trouvé lors du scraping",
                error="scraping_failed",
            )

        print(f"{len(articles)} articles collectés avec succès")

        # ── ÉTAPE 2 : ANALYSE AVEC GEMINI ET MÉMOIRE ────────────────
        print("\nEtape 2 — Analyse avec Gemini et mémoire long terme...")

        articles_content = ""
        for i, article in enumerate(articles, start=1):
            articles_content += f"""
--- Article {i} ---
Titre : {article.title}
Source : {article.source}
URL : {article.url}
Contenu :
{article.content[:1500]}

"""

        analysis = self.analyser_articles(articles_content)
        print(f"Analyse terminée — {len(analysis['trends'])} tendances identifiées")

        # ── ÉTAPE 3 : SAUVEGARDE EN MÉMOIRE LONG TERME ──────────────
        print("\nEtape 3 — Sauvegarde en mémoire long terme...")
        from services.memory_service import save_to_long_term

        # Sauvegarder chaque tendance identifiée
        for trend in analysis["trends"]:
            save_to_long_term(
                category="tendance",
                content=trend,
                source="NewsScraperAgent",
                importance=2,
            )

        # Sauvegarder le résumé global du rapport
        save_to_long_term(
            category="rapport_news",
            content=analysis["summary"][:500],
            source=f"Rapport du {datetime.now().strftime('%d/%m/%Y')}",
            importance=3,
        )

        print(f"Mémoire mise à jour — {len(analysis['trends'])} tendances sauvegardées")

        # ── ÉTAPE 4 : CONSTRUCTION DU RAPPORT ───────────────────────
        print("\nEtape 4 — Construction du rapport...")

        report = NewsReport(
            generated_at=datetime.now().strftime("%d/%m/%Y à %H:%M"),
            articles_found=len(articles),
            articles_analyzed=len(articles),
            summary=analysis["summary"],
            top_articles=articles,
            key_trends=analysis["trends"],
        )

        print("Rapport construit")

        # ── ÉTAPE 5 : ENVOI DE L'EMAIL ──────────────────────────────
        print("\nEtape 5 — Envoi de l'email...")
        email_sent = await send_news_report(report)

        if email_sent:
            print("Email envoyé avec succès")
        else:
            print("Echec de l'envoi d'email")

        print(f"\n{'='*60}")
        print("AGENT AUTONOME TERMINÉ")
        print(f"{'='*60}\n")

        return AgentRunResult(
            success=True,
            message=f"Rapport généré et email {'envoyé' if email_sent else 'non envoyé'}",
            report=report,
        )

    except Exception as e:
        print(f"\nERREUR AGENT : {e}")
        return AgentRunResult(
            success=False,
            message="Erreur lors de l'exécution de l'agent",
            error=str(e),
        )
