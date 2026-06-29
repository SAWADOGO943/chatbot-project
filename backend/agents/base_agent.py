from google import genai
import os
from dotenv import load_dotenv
import time

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
        """Sélectionne le modèle gemini-2.5-flash."""
        target_model = "gemini-2.5-flash"

        try:
            # On vérifie si le modèle cible est bien disponible dans la liste
            available_models = [m.name for m in self.client.models.list()]

            # Recherche exacte ou partielle selon la structure de retour de l'API
            if any(target_model in m for m in available_models):
                print(f"Modèle sélectionné : {target_model}")
                return target_model

        except Exception as e:
            print(f"Erreur lors du listage des modèles : {e}")

        # Fallback sécurisé
        return target_model

    # ── OUTILS GÉNÉRIQUES ──────────────────────────────────────────

    def _call_gemini(self, prompt: str, max_retries: int = 5) -> str:
        """Méthode interne pour centraliser les appels au LLM."""
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name, contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                error_str = str(e)

                # Si c'est une erreur 503 (surchargé), on réessaye plus longtemps
                if "503" in error_str or "UNAVAILABLE" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = (
                            3**attempt
                        )  # Backoff plus agressif: 1s, 3s, 9s, 27s, 81s
                        print(
                            f"⚠️  API surchargée — Retry dans {wait_time}s... (tentative {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                    else:
                        print(
                            f"❌ API toujours surchargée après {max_retries} tentatives"
                        )
                        raise
                else:
                    # Autres erreurs : ne pas réessayer
                    print(f"❌ Erreur API : {error_str}")
                    raise

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
