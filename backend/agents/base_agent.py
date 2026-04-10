from google import genai
import os
from dotenv import load_dotenv

load_dotenv()


class BaseAgent:
    """
    Classe de base pour tous nos agents.
    Utilise le nouveau SDK Google Gen AI (v1.0).
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Clé API Gemini manquante dans .env")

        # Initialisation du client (remplace genai.configure)
        self.client = genai.Client(api_key=api_key)
        self.model_name = self._select_model()

    def _select_model(self) -> str:
        """Sélectionne le nom du modèle à utiliser."""
        # On privilégie les versions 2.0 pour les agents
        models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]

        try:
            # On vérifie les modèles disponibles via le client
            for m in self.client.models.list():
                for candidate in models_to_try:
                    if candidate in m.name:
                        print(f"Modèle sélectionné : {candidate}")
                        return candidate
        except Exception as e:
            print(f"Erreur lors du listage des modèles : {e}")

        return "gemini-1.5-flash"  # Fallback sécurisé

    # ── OUTILS GÉNÉRIQUES ──────────────────────────────────────────

    def _call_gemini(self, prompt: str) -> str:
        """Méthode interne pour centraliser les appels au LLM."""
        response = self.client.models.generate_content(
            model=self.model_name, contents=prompt
        )
        return response.text.strip()

    def analyser_sentiment(self, texte: str) -> str:
        prompt = f"""Tu es un outil d'analyse de sentiment. Analyse ce texte :
        {texte}
        Réponds au format : VERDICT, INTENSITÉ, JUSTIFICATION, MOTS CLÉS."""
        return self._call_gemini(prompt)

    def extraire_themes(self, texte: str) -> str:
        prompt = f"""Identifie les thèmes principaux de ce texte :
        {texte}
        Réponds au format : THÈME PRINCIPAL, THÈMES SECONDAIRES, RÉSUMÉ."""
        return self._call_gemini(prompt)

    def evaluer_complexite(self, texte: str) -> str:
        prompt = f"""Évalue la complexité de ce texte :
        {texte}
        Réponds au format : NIVEAU, VOCABULAIRE, STRUCTURE, PUBLIC CIBLE."""
        return self._call_gemini(prompt)

    def synthetiser(self, texte_original: str, resultats_etapes: list) -> str:
        res_formates = "\n\n".join(
            [f"--- {r['nom']} ---\n{r['resultat']}" for r in resultats_etapes]
        )
        prompt = f"""Produis une synthèse finale :
        TEXTE ORIGINAL : {texte_original}
        RÉSULTATS : {res_formates}"""
        return self._call_gemini(prompt)
