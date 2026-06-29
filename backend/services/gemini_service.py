import os
from google import genai
from google.genai import types


async def call_gemini(user_message: str) -> str:
    """
    Envoie un message à Gemini via le SDK officiel google-genai.
    Retourne le texte généré.
    """

    # Récupération de la clé API
    api_key = os.getenv("GEMINI_API_KEY")

    print(f"\n{'=' * 50}")
    print(f"CLÉ LUE : {api_key[:20]}..." if api_key else "Aucune clé trouvée")
    print(f"{'=' * 50}\n")

    # Vérification de sécurité
    if not api_key:
        raise ValueError("GEMINI_API_KEY manquante dans le fichier .env")

    try:
        # Initialisation du client Gemini
        client = genai.Client(api_key=api_key)

        # Appel du modèle
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="high")
            ),
        )

        return response.text

    except Exception as e:
        raise Exception(f"Erreur Gemini : {str(e)}")
