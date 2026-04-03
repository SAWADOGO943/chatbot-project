from agents.base_agent import BaseAgent
from schemas.agent_schema import AgentResponse, AgentStep
from typing import List


class TextAnalysisAgent(BaseAgent):
    """
    Agent d'analyse de texte.
    Planifie, exécute et observe son propre travail.
    Son raisonnement complet est visible dans la réponse.
    """

    def __init__(self):
        super().__init__()  # Initialise Gemini via BaseAgent

        # Dictionnaire des outils disponibles
        # Clé = nom de l'outil, Valeur = la fonction à appeler
        self.tools = {
            "analyser_sentiment": self.analyser_sentiment,
            "extraire_themes": self.extraire_themes,
            "evaluer_complexite": self.evaluer_complexite,
        }

    def planifier(self, texte: str, task: str) -> List[str]:
        """
        Phase PLANIFICATION — L'agent décide lui-même quelles étapes effectuer.
        C'est ici que l'agent "réfléchit" avant d'agir.
        Il reçoit la liste des outils disponibles et choisit lesquels utiliser.
        """
        prompt = f"""Tu es un agent IA qui doit planifier une analyse de texte.
Ta tâche : {task}

Les outils disponibles :
- analyser_sentiment : analyse si le texte est positif, négatif ou neutre
- extraire_themes : identifie les thèmes principaux du texte
- evaluer_complexite : évalue le niveau de complexité du texte

En lisant ce texte, décide quels outils utiliser et dans quel ordre.
Réponds UNIQUEMENT avec une liste numérotée, une étape par ligne.
Format exact attendu :
1. [nom_outil] : [raison en une phrase]
2. [nom_outil] : [raison en une phrase]
3. [nom_outil] : [raison en une phrase]

Texte à analyser (aperçu) :
{texte[:500]}"""

        response = self.model.generate_content(prompt)
        plan_text = response.text.strip()

        # Parse la réponse pour extraire les étapes numérotées
        steps = []
        for line in plan_text.split("\\n"):
            line = line.strip()
            if line and line[0].isdigit():
                steps.append(line)

        # Sécurité : si le parsing échoue, on utilise un plan par défaut
        if not steps:
            steps = [
                "1. analyser_sentiment : comprendre le ton général du texte",
                "2. extraire_themes : identifier les sujets principaux abordés",
                "3. evaluer_complexite : évaluer le niveau requis pour lire ce texte",
            ]

        return steps

    def _identifier_outil(self, etape: str) -> str:
        """
        Identifie quel outil utiliser en lisant le nom dans l'étape du plan.
        Cherche le nom de l'outil dans le texte de l'étape.
        """
        etape_lower = etape.lower()
        for tool_name in self.tools.keys():
            if tool_name in etape_lower:
                return tool_name

        # Fallback : prend le premier outil si aucun n'est trouvé
        return list(self.tools.keys())[0]

    def observer(self, etape_nom: str, resultat: str) -> str:
        """
        Phase OBSERVATION — L'agent lit son propre résultat.
        Il formule ce qu'il a appris en une ou deux phrases.
        Cette étape simule la réflexion de l'agent sur ses propres actions.
        """
        prompt = f"""Tu es un agent IA qui vient d'exécuter une étape de son analyse.
Observe le résultat et formule en 1 ou 2 phrases ce que tu retiens.
Commence obligatoirement par "J'observe que..."
Sois concis et factuel.

Etape exécutée : {etape_nom}
Résultat obtenu :
{resultat}"""

        response = self.model.generate_content(prompt)
        return response.text.strip()

    async def run(self, texte: str, task: str) -> AgentResponse:
        """
        Boucle principale de l'agent.
        Planifier -> Executer chaque étape -> Observer -> Synthétiser.
        """

        print(f"\\n{'=' * 50}")
        print(f"AGENT DÉMARRÉ")
        print(f"Tâche : {task}")
        print(f"{'=' * 50}\\n")

        # ── PHASE 1 : PLANIFICATION ──────────────────────────────────
        print("Phase 1 — Planification en cours...")
        plan = self.planifier(texte, task)
        print(f"Plan établi : {len(plan)} étapes")
        for etape in plan:
            print(f"  {etape}")

        # ── PHASE 2 : EXÉCUTION ET OBSERVATION ──────────────────────
        steps_executed = []
        resultats_pour_synthese = []

        for i, etape in enumerate(plan, start=1):
            print(f"\\nPhase 2.{i} — Exécution : {etape}")

            # Identifier l'outil à utiliser
            tool_name = self._identifier_outil(etape)
            tool_function = self.tools[tool_name]

            # Extraire le nom lisible de l'étape
            step_name = etape.split(":")[1].strip() if ":" in etape else etape

            # Exécuter l'outil
            print(f"  Outil utilisé : {tool_name}")
            result = tool_function(texte)
            print(f"  Résultat obtenu ({len(result)} caractères)")

            # Observer le résultat
            observation = self.observer(tool_name, result)
            print(f"  Observation : {observation[:100]}...")

            # Stocker l'étape complète
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

        # ── PHASE 3 : SYNTHÈSE FINALE ────────────────────────────────
        print(f"\\nPhase 3 — Synthèse finale en cours...")
        final_answer = self.synthetiser(texte, resultats_pour_synthese)
        print("Synthèse générée.")

        print(f"\\n{'=' * 50}")
        print("AGENT TERMINÉ")
        print(f"{'=' * 50}\\n")

        return AgentResponse(
            task=task,
            plan=plan,
            steps=steps_executed,
            final_answer=final_answer,
            total_steps=len(steps_executed),
        )
