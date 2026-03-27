import httpx  # Importation de la bibliothèque pour les requêtes HTTP asynchrones
import os  # Importation du module système pour accéder aux variables d'environnement

# Liste des modèles testés dans l'ordre de préférence
# Si le premier ne marche pas, on essaie le suivant automatiquement
MODELS_TO_TRY = [
    "gemini-2.5-flash",  # Modèle cible prioritaire (futuriste/hypothétique)
    "gemini-2.0-flash",  # Version flash actuelle performante
    "gemini-2.0-flash-exp",  # Version expérimentale 2.0
    "gemini-1.5-flash",  # Modèle rapide et léger de la génération 1.5
    "gemini-1.5-flash-8b",  # Version encore plus légère (8 milliards de paramètres)
    "gemini-1.5-pro",  # Modèle haute performance (plus lent/coûteux)
    "gemini-pro",  # Modèle original de la gamme Pro
]


async def call_gemini(user_message: str) -> str:
    """
    Envoie un message à Gemini.
    Teste automatiquement les modèles disponibles jusqu'à en trouver un qui fonctionne.
    """

    # Récupération de la clé API depuis les variables d'environnement du système
    api_key = os.getenv("GEMINI_API_KEY")

    # Affichage cosmétique pour le débogage (barre de séparation)
    print(f"\n{'=' * 50}")
    # Affiche les 20 premiers caractères de la clé pour vérifier qu'elle est bien chargée
    print(f"CLÉ LUE : {api_key[:20]}...")
    print(f"{'=' * 50}\n")

    # Vérification de sécurité : si la clé est vide ou None, on arrête tout
    if not api_key:
        raise ValueError("GEMINI_API_KEY manquante dans le fichier .env")

    # Construction de la structure JSON attendue par l'API Google Generative AI
    payload = {"contents": [{"parts": [{"text": user_message}]}]}

    # Ouverture d'un client HTTP asynchrone avec un délai d'attente de 30 secondes
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Boucle principale : on parcourt la liste des noms de modèles définie plus haut
        for model in MODELS_TO_TRY:
            # Sous-boucle : l'API Google peut être en version stable (v1) ou bêta (v1beta)
            for api_version in ["v1", "v1beta"]:
                # Construction dynamique de l'URL avec la version, le modèle et la clé API
                url = (
                    f"https://generativelanguage.googleapis.com/{api_version}"
                    f"/models/{model}:generateContent?key={api_key}"
                )

                # Information dans la console pour suivre l'avancement du script
                print(f"🔄 Tentative : {model} ({api_version})")

                try:
                    # Envoi de la requête POST avec le contenu (payload) au format JSON
                    response = await client.post(url, json=payload)

                    # Si le modèle spécifié n'existe pas ou n'est pas accessible (Erreur 404)
                    if response.status_code == 404:
                        print(
                            f"❌ {model} ({api_version}) → NOT FOUND, on passe au suivant"
                        )
                        continue  # Passe à l'itération suivante de la boucle (version ou modèle)

                    # Si la limite de requêtes est atteinte pour ce modèle (Erreur 429)
                    if response.status_code == 429:
                        print(
                            f"❌ {model} ({api_version}) → QUOTA DÉPASSÉ, on passe au suivant"
                        )
                        continue  # On tente le modèle suivant qui a peut-être son propre quota

                    # Vérifie si la réponse est un succès (200), sinon lève une exception HTTP
                    response.raise_for_status()

                    # Conversion de la réponse brute en dictionnaire Python
                    data = response.json()
                    # Extraction de la réponse textuelle dans la hiérarchie complexe du JSON de Google
                    reply = data["candidates"][0]["content"]["parts"][0]["text"]

                    # Message de succès et sortie immédiate de la fonction avec le texte généré
                    print(f"✅ Succès avec : {model} ({api_version})")
                    return reply

                # Gestion des erreurs HTTP spécifiques (ex: 400, 500)
                except httpx.HTTPStatusError:
                    print(
                        f"❌ {model} ({api_version}) → ERREUR HTTP, on passe au suivant"
                    )
                    continue

                # Gestion des erreurs de connexion réseau (DNS, timeout, etc.)
                except httpx.RequestError as e:
                    raise Exception(f"Erreur réseau: {str(e)}")

                # Gestion du cas où le JSON reçu n'a pas la structure attendue
                except (KeyError, IndexError):
                    print(
                        f"❌ {model} ({api_version}) → FORMAT INATTENDU, on passe au suivant"
                    )
                    continue

        # Si le code arrive ici, c'est qu'aucune combinaison modèle/version n'a fonctionné
        raise Exception(
            "Aucun modèle Gemini disponible pour cette clé API. "
            "Vérifie ton quota sur https://ai.google.dev/gemini-api/docs/rate-limits"
        )
