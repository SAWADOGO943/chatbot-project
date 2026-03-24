from pydantic import BaseModel

# Ce que le frontend DOIT envoyer
class ChatRequest(BaseModel):
    message: str  # Obligatoire, doit être une chaîne de caractères

# Ce que le backend VA retourner
class ChatResponse(BaseModel):
    reply: str  # La réponse générée par Gemini