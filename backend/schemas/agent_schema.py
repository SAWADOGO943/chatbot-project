from pydantic import BaseModel
from typing import List, Optional


class AgentStep(BaseModel):
    """Représente une étape du raisonnement de l'agent"""

    step_number: int  # Numéro de l'étape (1, 2, 3...)
    step_name: str  # Nom lisible de l'étape
    tool_used: str  # Nom de l'outil utilisé
    result: str  # Résultat brut retourné par l'outil
    observation: str  # Ce que l'agent a retenu de ce résultat


class AgentResponse(BaseModel):
    """Réponse complète de l'agent avec tout son raisonnement visible"""

    task: str  # La tâche reçue
    plan: List[str]  # Le plan établi par l'agent
    steps: List[AgentStep]  # Chaque étape exécutée
    final_answer: str  # La synthèse finale
    total_steps: int  # Nombre total d'étapes exécutées


class AgentRequest(BaseModel):
    """Requête envoyée à l'agent"""

    text: str  # Le texte à analyser
    task: Optional[str] = "Analyse complète de ce texte"  # La tâche (optionnelle)
