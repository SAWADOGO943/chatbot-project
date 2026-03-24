import httpx
import os

# Liste des modèles testés dans l'ordre de préférence
# Si le premier ne marche pas, on essaie le suivant automatiquement
MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-pro",
]


async def call_gemini(user_message: str) -> str:
    """
    Envoie un message à Gemini.
    Teste automatiquement les modèles disponibles jusqu'à en trouver un qui fonctionne.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    print(f"\n{'=' * 50}")
    print(f"CLÉ LUE : {api_key[:20]}...")
    print(f"{'=' * 50}\n")

    if not api_key:
        raise ValueError("GEMINI_API_KEY manquante dans le fichier .env")

    payload = {"contents": [{"parts": [{"text": user_message}]}]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # On teste chaque modèle un par un
        for model in MODELS_TO_TRY:
            # On essaie d'abord v1, puis v1beta si v1 ne marche pas
            for api_version in ["v1", "v1beta"]:
                url = (
                    f"https://generativelanguage.googleapis.com/{api_version}"
                    f"/models/{model}:generateContent?key={api_key}"
                )

                print(f"🔄 Tentative : {model} ({api_version})")

                try:
                    response = await client.post(url, json=payload)

                    # Modèle non trouvé → on essaie le suivant
                    if response.status_code == 404:
                        print(
                            f"❌ {model} ({api_version}) → NOT FOUND, on passe au suivant"
                        )
                        continue

                    # Quota dépassé → on essaie le suivant
                    if response.status_code == 429:
                        print(
                            f"❌ {model} ({api_version}) → QUOTA DÉPASSÉ, on passe au suivant"
                        )
                        continue

                    # Autre erreur → on lève une exception
                    response.raise_for_status()

                    data = response.json()
                    reply = data["candidates"][0]["content"]["parts"][0]["text"]

                    print(f"✅ Succès avec : {model} ({api_version})")
                    return reply

                except httpx.HTTPStatusError:
                    print(
                        f"❌ {model} ({api_version}) → ERREUR HTTP, on passe au suivant"
                    )
                    continue

                except httpx.RequestError as e:
                    raise Exception(f"Erreur réseau: {str(e)}")

                except (KeyError, IndexError):
                    print(
                        f"❌ {model} ({api_version}) → FORMAT INATTENDU, on passe au suivant"
                    )
                    continue

        # Si aucun modèle n'a fonctionné
        raise Exception(
            "Aucun modèle Gemini disponible pour cette clé API. "
            "Vérifie ton quota sur https://ai.google.dev/gemini-api/docs/rate-limits"
        )
