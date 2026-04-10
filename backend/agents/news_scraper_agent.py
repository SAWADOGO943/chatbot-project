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
    Scrape les actus tech, les analyse avec Gemini, envoie un email.
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
[Synthèse factuelle et précise en 4 à 6 phrases]

TENDANCES:
- [Tendance 1]
- [Tendance 2]
- [Tendance 3]

ANALYSE:
[Signification pour le secteur tech en 2-3 phrases]"""

        try:
            # Appel sécurisé au client Gemini (SDK v1.0)
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt
            )
            text = response.text.strip()
        except Exception as e:
            # Gestion de la saturation (Erreur 503)
            print(f"⚠️ ERREUR GEMINI (Analyse) : {e}")
            return {
                "summary": "L'analyse détaillée est momentanément indisponible (serveurs saturés). Veuillez consulter les sources ci-dessous.",
                "trends": ["Service IA saturé - Réessai au prochain cycle"],
            }

        # --- Logique de Parsing ---
        summary = ""
        if "RÉSUMÉ_GLOBAL:" in text:
            parts = text.split("RÉSUMÉ_GLOBAL:")
            if len(parts) > 1:
                summary = parts[1].split("TENDANCES:")[0].strip()

        trends = []
        if "TENDANCES:" in text:
            parts = text.split("TENDANCES:")
            if len(parts) > 1:
                trends_part = parts[1].split("ANALYSE:")[0].strip()
                # Nettoyage propre des lignes de tendances
                trends = [
                    line.strip("- ").strip()
                    for line in trends_part.split("\n")
                    if line.strip().startswith("-")
                ]

        if "ANALYSE:" in text:
            parts = text.split("ANALYSE:")
            if len(parts) > 1:
                analyse_finale = parts[1].strip()
                summary = (
                    f"{summary}\n\n{analyse_finale}" if summary else analyse_finale
                )

        return {
            "summary": summary or text[:1000],
            "trends": trends or ["Analyse des tendances indisponible"],
        }

    async def run(self) -> AgentRunResult:
        """
        Boucle principale de l'agent autonome.
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
            articles_content = "".join(
                [
                    f"\n--- Article {i} ---\nTitre: {a.title}\nContenu: {a.content[:1500]}\n"
                    for i, a in enumerate(articles, 1)
                ]
            )

            analysis = self.analyser_articles(articles_content)
            print(f"Analyse terminée — {len(analysis['trends'])} tendances identifiées")

            # ── ÉTAPE 3 : CONSTRUCTION DU RAPPORT ───────────────────────
            report = NewsReport(
                generated_at=datetime.now().strftime("%d/%m/%Y à %H:%M"),
                articles_found=len(articles),
                articles_analyzed=len(articles),
                summary=analysis["summary"],
                top_articles=articles,
                key_trends=analysis["trends"],
            )

            # ── ÉTAPE 4 : ENVOI DE L'EMAIL ──────────────────────────────
            print("\nEtape 4 — Envoi de l'email...")
            email_sent = await send_news_report(report)

            status_msg = (
                "envoyé avec succès"
                if email_sent
                else "non envoyé (erreur service email)"
            )

            print(f"\n{'=' * 60}")
            print("AGENT AUTONOME TERMINÉ")
            print(f"{'=' * 60}\n")

            return AgentRunResult(
                success=True,
                message=f"Rapport généré et email {status_msg}",
                report=report,
            )

        except Exception as e:
            print(f"\nERREUR CRITIQUE AGENT : {e}")
            return AgentRunResult(
                success=False,
                message="Erreur fatale lors de l'exécution",
                error=str(e),
            )
