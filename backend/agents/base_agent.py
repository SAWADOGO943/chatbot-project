import os
import google.generativeai as genai


class BaseAgent:
    """
    Classe de base pour tous nos agents.
    Contient la connexion à Gemini et les outils partagés.
    Tous les agents héritent de cette classe.
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Clé API Gemini manquante dans .env")

        genai.configure(api_key=api_key)
        self.model = self._init_model()

    def _init_model(self):
        """Sélectionne automatiquement le meilleur modèle disponible"""
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]

        try:
            available = {
                m.name.replace("models/", "")
                for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            }
            for candidate in models_to_try:
                if candidate in available:
                    print(f"Modèle sélectionné : {candidate}")
                    return genai.GenerativeModel(candidate)
        except Exception:
            pass

        # Fallback si list_models échoue
        print("Fallback : gemini-1.5-flash")
        return genai.GenerativeModel("gemini-1.5-flash")

    # ── OUTILS ──────────────────────────────────────────────────────

    def analyser_sentiment(self, texte: str) -> str:
        """
        Outil 1 — Analyse le sentiment d'un texte.
        Retourne : Positif, Négatif, Neutre ou Mixte avec justification.
        """
        prompt = f"""Tu es un outil d'analyse de sentiment.
Analyse le sentiment de ce texte de manière précise.
Réponds dans ce format exact :

VERDICT : [Positif / Négatif / Neutre / Mixte]
INTENSITÉ : [Faible / Modérée / Forte]
JUSTIFICATION : [2 à 3 phrases expliquant pourquoi]
MOTS CLÉS RÉVÉLATEURS : [liste de 3 à 5 mots qui révèlent le sentiment]

Texte à analyser :
{texte}"""

        response = self.model.generate_content(prompt)
        return response.text.strip()

    def extraire_themes(self, texte: str) -> str:
        """
        Outil 2 — Extrait les thèmes principaux d'un texte.
        Retourne une liste structurée de thèmes avec description.
        """
        prompt = f"""Tu es un outil d'extraction de thèmes.
Identifie les thèmes principaux de ce texte.
Réponds dans ce format exact :

THÈME PRINCIPAL : [le thème dominant]
THÈMES SECONDAIRES :
- [thème 2] : [description en une phrase]
- [thème 3] : [description en une phrase]
- [thème 4 si présent] : [description en une phrase]
RÉSUMÉ EN UNE PHRASE : [résumé global du contenu]

Texte à analyser :
{texte}"""

        response = self.model.generate_content(prompt)
        return response.text.strip()

    def evaluer_complexite(self, texte: str) -> str:
        """
        Outil 3 — Évalue la complexité et le niveau d'un texte.
        Retourne une évaluation du niveau de lecture requis.
        """
        prompt = f"""Tu es un outil d'évaluation de complexité textuelle.
Évalue la complexité de ce texte.
Réponds dans ce format exact :

NIVEAU : [Débutant / Intermédiaire / Avancé / Expert]
VOCABULAIRE : [Simple / Technique / Spécialisé]
STRUCTURE : [Claire / Complexe / Très complexe]
PUBLIC CIBLE : [description du lecteur idéal en une phrase]
CONSEIL : [une recommandation concrète pour l'auteur ou le lecteur]

Texte à analyser :
{texte}"""

        response = self.model.generate_content(prompt)
        return response.text.strip()

    def synthetiser(self, texte_original: str, resultats_etapes: list) -> str:
        """
        Outil 4 — Synthétise tous les résultats en une réponse finale.
        C'est l'outil de conclusion — toujours appelé en dernier.
        """
        resultats_formates = "\\n\\n".join(
            [f"--- {r['nom']} ---\\n{r['resultat']}" for r in resultats_etapes]
        )

        prompt = f"""Tu es un agent IA qui vient de terminer son analyse.
Tu as exécuté plusieurs étapes et obtenu des résultats.
Produis maintenant une synthèse finale claire et utile.

TEXTE ORIGINAL :
{texte_original}

RÉSULTATS DE TON ANALYSE :
{resultats_formates}

Ta synthèse finale doit :
1. Donner un verdict global en 1 phrase
2. Présenter les 3 points les plus importants découverts
3. Formuler une recommandation concrète
4. Conclure avec une phrase de synthèse

Sois direct, précis et utile."""

        response = self.model.generate_content(prompt)
        return response.text.strip()
