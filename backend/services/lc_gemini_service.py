import os
from langchain_google_genai import ChatGoogleGenerativeAI


def get_langchain_model() -> ChatGoogleGenerativeAI:
    """
    Retourne un modèle Gemini compatible LangChain.
    Ce modèle peut être utilisé dans n'importe quelle Chain.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Clé API Gemini manquante dans .env")

    return ChatGoogleGenerativeAI(
        model="Gemini 2.5 Flash-",
        google_api_key=api_key,
        temperature=0.3,  # 0 = réponses stables, 1 = créatives
    )
