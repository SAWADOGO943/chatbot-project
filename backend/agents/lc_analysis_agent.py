import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from schemas.agent_schema import AgentResponse, AgentStep
from typing import List
import asyncio


# ── TEMPLATES DE PROMPTS ──────────────────────────────────────────────
# Séparés du code — plus faciles à modifier et à tester indépendamment

PROMPT_SENTIMENT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Tu es un outil d'analyse de sentiment.
Analyse le sentiment du texte fourni de manière précise.
Réponds dans ce format exact :

VERDICT : [Positif / Négatif / Neutre / Mixte]
INTENSITÉ : [Faible / Modérée / Forte]
JUSTIFICATION : [2 à 3 phrases expliquant pourquoi]
MOTS CLÉS RÉVÉLATEURS : [liste de 3 à 5 mots qui révèlent le sentiment]""",
        ),
        ("human", "Texte à analyser :\n{texte}"),
    ]
)

PROMPT_THEMES = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Tu es un outil d'extraction de thèmes.
Identifie les thèmes principaux du texte fourni.
Réponds dans ce format exact :

THÈME PRINCIPAL : [le thème dominant]
THÈMES SECONDAIRES :
- [thème 2] : [description en une phrase]
- [thème 3] : [description en une phrase]
RÉSUMÉ EN UNE PHRASE : [résumé global du contenu]""",
        ),
        ("human", "Texte à analyser :\n{texte}"),
    ]
)

PROMPT_COMPLEXITE = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Tu es un outil d'évaluation de complexité textuelle.
Évalue la complexité du texte fourni.
Réponds dans ce format exact :

NIVEAU : [Débutant / Intermédiaire / Avancé / Expert]
VOCABULAIRE : [Simple / Technique / Spécialisé]
STRUCTURE : [Claire / Complexe / Très complexe]
PUBLIC CIBLE : [description du lecteur idéal en une phrase]
CONSEIL : [une recommandation concrète]""",
        ),
        ("human", "Texte à analyser :\n{texte}"),
    ]
)

PROMPT_SYNTHESE = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Tu es un agent IA qui synthétise les résultats d'une analyse.
Produis une synthèse finale claire et utile.
Ta synthèse doit :
1. Donner un verdict global en 1 phrase
2. Présenter les 3 points les plus importants découverts
3. Formuler une recommandation concrète
4. Conclure avec une phrase de synthèse

Sois direct, précis et utile.""",
        ),
        (
            "human",
            """Texte original :
{texte_original}

Résultats de l'analyse :
{resultats}""",
        ),
    ]
)


class LCAnalysisAgent:
    """
    Agent d'analyse de texte — version LangChain.
    Fait exactement la même chose que TextAnalysisAgent (semaine 13)
    mais avec des Chains au lieu de generate_content() manuel.
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Clé API Gemini manquante dans .env")

        # Un seul modèle partagé entre toutes les chains
        self.model = ChatGoogleGenerativeAI(
            model="Gemini 2.5 Flash",
            google_api_key=api_key,
            temperature=0.3,
        )

        # Parser commun à toutes les chains
        self.parser = StrOutputParser()

        # Construction des chains au démarrage
        self._build_chains()
        print("LCAnalysisAgent initialisé avec LangChain")

    def _build_chains(self):
        """
        Construit toutes les chains une seule fois au démarrage.
        Chaque chain = prompt | modèle | parser.
        """
        self.chain_sentiment = PROMPT_SENTIMENT | self.model | self.parser
        self.chain_themes = PROMPT_THEMES | self.model | self.parser
        self.chain_complexite = PROMPT_COMPLEXITE | self.model | self.parser
        self.chain_synthese = PROMPT_SYNTHESE | self.model | self.parser

        print("4 chains construites : sentiment, themes, complexite, synthese")

    # ── OUTILS — même interface qu'avant, implémentation LangChain ────

    def analyser_sentiment(self, texte: str) -> str:
        """Analyse le sentiment — utilise chain_sentiment"""
        return self.chain_sentiment.invoke({"texte": texte})

    def extraire_themes(self, texte: str) -> str:
        """Extrait les thèmes — utilise chain_themes"""
        return self.chain_themes.invoke({"texte": texte})

    def evaluer_complexite(self, texte: str) -> str:
        """Évalue la complexité — utilise chain_complexite"""
        return self.chain_complexite.invoke({"texte": texte})

    def synthetiser(self, texte_original: str, resultats: list) -> str:
        """Synthèse finale — utilise chain_synthese"""
        resultats_formates = "\n\n".join(
            [f"--- {r['nom']} ---\n{r['resultat']}" for r in resultats]
        )
        return self.chain_synthese.invoke(
            {
                "texte_original": texte_original,
                "resultats": resultats_formates,
            }
        )

    # ── PLANIFICATION ─────────────────────────────────────────────────

    def planifier(self, texte: str, task: str) -> List[str]:
        """
        Planifie les étapes d'analyse.
        Même logique qu'en semaine 13 — avec une chain LangChain.
        """
        prompt_planif = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Tu es un agent IA qui planifie une analyse de texte.
Les outils disponibles :
- analyser_sentiment : analyse si le texte est positif, négatif ou neutre
- extraire_themes : identifie les thèmes principaux du texte
- evaluer_complexite : évalue le niveau de complexité du texte

Décide quels outils utiliser et dans quel ordre.
Réponds UNIQUEMENT avec une liste numérotée, une étape par ligne.
Format : 1. [nom_outil] : [raison en une phrase]""",
                ),
                ("human", "Tâche : {task}\n\nTexte (aperçu) :\n{texte}"),
            ]
        )

        chain_planif = prompt_planif | self.model | self.parser

        try:
            plan_text = chain_planif.invoke({"task": task, "texte": texte[:500]})
            print(f"DEBUG — Réponse Gemini (planification) :\n{plan_text}\n")
        except Exception as e:
            print(f"❌ Erreur lors de la planification : {e}")
            return [
                "1. analyser_sentiment : comprendre le ton général",
                "2. extraire_themes : identifier les sujets principaux",
                "3. evaluer_complexite : évaluer le niveau de lecture",
            ]

        steps = []
        for line in plan_text.split("\n"):
            line = line.strip()
            if line and len(line) > 0 and line[0].isdigit():
                steps.append(line)

        if not steps:
            print("⚠️  Aucune étape numérotée trouvée — utilisation du fallback")
            steps = [
                "1. analyser_sentiment : comprendre le ton général",
                "2. extraire_themes : identifier les sujets principaux",
                "3. evaluer_complexite : évaluer le niveau de lecture",
            ]

        return steps

    def observer(self, etape_nom: str, resultat: str) -> str:
        """
        Phase observation — même logique qu'en semaine 13.
        """
        prompt_obs = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Tu es un agent IA qui observe son propre travail.
Formule en 1 ou 2 phrases ce que tu retiens du résultat.
Commence obligatoirement par "J'observe que..."
Sois concis et factuel.""",
                ),
                ("human", "Étape : {etape}\nRésultat :\n{resultat}"),
            ]
        )

        chain_obs = prompt_obs | self.model | self.parser

        return chain_obs.invoke({"etape": etape_nom, "resultat": resultat})

    # ── BOUCLE PRINCIPALE — identique à TextAnalysisAgent ─────────────

    async def run(self, texte: str, task: str) -> AgentResponse:
        """
        Même boucle qu'en semaine 13 :
        Planifier -> Exécuter -> Observer -> Synthétiser
        La différence est invisible ici — elle est dans les méthodes au-dessus.
        """
        print(f"\n{'=' * 50}")
        print("LC AGENT DÉMARRÉ (LangChain)")
        print(f"Tâche : {task}")
        print(f"{'=' * 50}\n")

        tools = {
            "analyser_sentiment": self.analyser_sentiment,
            "extraire_themes": self.extraire_themes,
            "evaluer_complexite": self.evaluer_complexite,
        }

        # Phase 1 — Planification
        print("Phase 1 — Planification...")
        plan = await asyncio.to_thread(self.planifier, texte, task)

        # Phase 2 — Exécution et observation
        steps_executed = []
        resultats_pour_synthese = []

        for i, etape in enumerate(plan, start=1):
            print(f"\nPhase 2.{i} — {etape}")

            # Identifier l'outil
            tool_name = list(tools.keys())[0]  # fallback
            for name in tools:
                if name in etape.lower():
                    tool_name = name
                    break

            step_name = etape.split(":")[1].strip() if ":" in etape else etape

            # Exécuter
            result = await asyncio.to_thread(tools[tool_name], texte)
            observation = await asyncio.to_thread(self.observer, tool_name, result)

            steps_executed.append(
                AgentStep(
                    step_number=i,
                    step_name=step_name,
                    tool_used=tool_name,
                    result=result,
                    observation=observation,
                )
            )

            resultats_pour_synthese.append(
                {
                    "nom": tool_name,
                    "resultat": result,
                }
            )

        # Phase 3 — Synthèse
        print("\nPhase 3 — Synthèse finale...")
        final_answer = await asyncio.to_thread(
            self.synthetiser, texte, resultats_pour_synthese
        )

        print(f"\n{'=' * 50}")
        print("LC AGENT TERMINÉ")
        print(f"{'=' * 50}\n")

        return AgentResponse(
            task=task,
            plan=plan,
            steps=steps_executed,
            final_answer=final_answer,
            total_steps=len(steps_executed),
        )
