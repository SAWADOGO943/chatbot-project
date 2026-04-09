import os
from datetime import datetime
from agents.base_agent import BaseAgent
from services.scraper_service import scrape_tech_news
from services.email_service import send_news_report
from schemas.news_schema import NewsReport, AgentRunResult
from typing import List
import google.generativeai as genai
from duckduckgo_search import DDGS


class NewsScraperAgent(BaseAgent):
    """
    Agent autonome de veille technologique.
    S'exécute automatiquement toutes les 12 heures.
    Scrape les actus tech, les analyse avec Gemini, envoie un email.
    Aucune intervention humaine requise. ba
    """

    def __init__(self):
        super().__init__()
        print("NewsScraperAgent initialisé et prêt")

    def analyser_articles(self, articles_content: str) -> dict:
        """
        Envoie tous les articles à Gemini pour analyse globale.
        Retourne un résumé et les tendances identifiées.
        """
        prompt = f"""Tu es un agent de veille technologique expert.
Tu viens de scraper plusieurs articles tech sur internet.
Analyse l'ensemble de ces articles et produis un rapport structuré.

ARTICLES SCRAPÉS :
{articles_content}

Produis ton analyse dans ce format EXACT — respecte les séparateurs :

RÉSUMÉ_GLOBAL:
[Un résumé en 4 à 6 phrases de ce qui se passe dans le monde tech en ce moment.
Synthétise les informations les plus importantes. Sois factuel et précis.]

TENDANCES:
- [Tendance 1 identifiée dans les articles]
- [Tendance 2 identifiée dans les articles]
- [Tendance 3 identifiée dans les articles]
- [Tendance 4 si présente]
- [Tendance 5 si présente]

ANALYSE:
[2 à 3 phrases sur ce que ces tendances signifient pour le secteur tech en général.]"""

        response = self.model.generate_content(prompt)
        text = response.text.strip()

        # Parse le résumé
        summary = ""
        if "RÉSUMÉ_GLOBAL:" in text:
            parts = text.split("RÉSUMÉ_GLOBAL:")
            if len(parts) > 1:
                summary_part = parts[1].split("TENDANCES:")[0].strip()
                summary = summary_part

        # Parse les tendances
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

        # Ajoute l'analyse au résumé si présente
        if "ANALYSE:" in text:
            parts = text.split("ANALYSE:")
            if len(parts) > 1:
                analyse = parts[1].strip()
                summary = summary + "\n\n" + analyse if summary else analyse

        # Sécurité : si le parsing échoue, on retourne le texte brut
        if not summary:
            summary = text[:1000]
        if not trends:
            trends = ["Analyse des tendances indisponible"]

        return {
            "summary": summary,
            "trends": trends,
        }

    async def run(self) -> AgentRunResult:
        """
        Boucle principale de l'agent autonome.
        Cette méthode est appelée automatiquement par APScheduler.
        """
        print(f"\n{'=' * 60}")
        print(f"AGENT AUTONOME DÉMARRÉ")
        print(f"Heure : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}\n")

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

            # ── ÉTAPE 2 : ANALYSE AVEC GEMINI ───────────────────────────
            print("\nEtape 2 — Analyse avec Gemini...")

            # Formate tous les articles pour Gemini
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

            # ── ÉTAPE 3 : CONSTRUCTION DU RAPPORT ───────────────────────
            print("\nEtape 3 — Construction du rapport...")

            report = NewsReport(
                generated_at=datetime.now().strftime("%d/%m/%Y à %H:%M"),
                articles_found=len(articles),
                articles_analyzed=len(articles),
                summary=analysis["summary"],
                top_articles=articles,
                key_trends=analysis["trends"],
            )

            print("Rapport construit")

            # ── ÉTAPE 4 : ENVOI DE L'EMAIL ──────────────────────────────
            print("\nEtape 4 — Envoi de l'email...")
            email_sent = await send_news_report(report)

            if email_sent:
                print("Email envoyé avec succès")
            else:
                print("Echec de l'envoi d'email")

            print(f"\n{'=' * 60}")
            print("AGENT AUTONOME TERMINÉ")
            print(f"{'=' * 60}\n")

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
