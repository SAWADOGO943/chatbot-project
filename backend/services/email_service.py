import os  # Importation du module pour interagir avec le système d'exploitation
import resend  # Importation du SDK de Resend pour l'envoi d'emails
from schemas.news_schema import (
    NewsReport,
)  # Importation de la classe de données NewsReport
from datetime import datetime  # Importation de la gestion des dates


def init_resend():
    """Configure Resend avec la clé API"""
    api_key = os.getenv(
        "RESEND_API_KEY"
    )  # Récupération de la clé API depuis les variables d'environnement
    if not api_key:  # Vérification de l'existence de la clé
        raise ValueError(
            "RESEND_API_KEY manquante dans .env"
        )  # Erreur si la clé n'est pas configurée
    resend.api_key = api_key  # Affectation de la clé au SDK Resend


def build_email_html(report: NewsReport) -> str:
    """
    Construit le HTML de l'email à partir du rapport.
    Un email HTML bien structuré et lisible.
    """

    # Construction des articles en HTML
    articles_html = (
        ""  # Initialisation de la chaîne de caractères pour le bloc articles
    )
    for i, article in enumerate(
        report.top_articles, start=1
    ):  # Boucle sur les articles avec indexation
        articles_html += f"""
        <div style="margin-bottom: 20px; padding: 15px;
                    background: #f8f9fa; border-radius: 8px;
                    border-left: 4px solid #4F46E5;">
            <h3 style="margin: 0 0 8px 0; color: #1a1a2e; font-size: 16px;">
                {i}. {article.title}
            </h3>
            <p style="margin: 0 0 8px 0; color: #666; font-size: 13px;">
                Source : <a href="{article.url}" style="color: #4F46E5;">
                {article.source}</a>
            </p>
            <p style="margin: 0; color: #444; font-size: 14px; line-height: 1.5;">
                {article.content[:300]}...
            </p>
        </div>
        """  # Concaténation du bloc HTML pour chaque article (limité à 300 caractères)

    # Construction des tendances en HTML
    trends_html = ""  # Initialisation de la chaîne pour les tendances
    for (
        trend
    ) in report.key_trends:  # Boucle sur la liste des tendances extraites par l'IA
        trends_html += f"""
        <li style="margin-bottom: 8px; color: #444; font-size: 14px;">
            {trend}
        </li>
        """  # Ajout d'une puce HTML pour chaque tendance

    # Template HTML complet
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                 sans-serif; background: #f0f2f5; margin: 0; padding: 20px;">

        <div style="max-width: 680px; margin: 0 auto; background: white;
                    border-radius: 16px; overflow: hidden;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.08);">

            <div style="background: linear-gradient(135deg, #4F46E5, #7C3AED);
                        padding: 32px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">
                    Rapport Tech — Agent IA
                </h1>
                <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0;
                           font-size: 14px;">
                    Généré automatiquement le {report.generated_at}
                </p>
            </div>

            <div style="display: flex; padding: 24px; gap: 16px;
                        background: #fafafa; border-bottom: 1px solid #eee;">
                <div style="flex: 1; text-align: center;">
                    <div style="font-size: 28px; font-weight: 700;
                                color: #4F46E5;">{report.articles_found}</div>
                    <div style="font-size: 12px; color: #666;">Articles trouvés</div>
                </div>
                <div style="flex: 1; text-align: center;">
                    <div style="font-size: 28px; font-weight: 700;
                                color: #4F46E5;">{report.articles_analyzed}</div>
                    <div style="font-size: 12px; color: #666;">Articles analysés</div>
                </div>
                <div style="flex: 1; text-align: center;">
                    <div style="font-size: 28px; font-weight: 700;
                                color: #4F46E5;">{len(report.key_trends)}</div>
                    <div style="font-size: 12px; color: #666;">Tendances clés</div>
                </div>
            </div>

            <div style="padding: 32px;">

                <h2 style="color: #1a1a2e; font-size: 18px;
                           margin: 0 0 16px 0; border-bottom: 2px solid #4F46E5;
                           padding-bottom: 8px;">
                    Résumé de l'agent
                </h2>
                <div style="background: #f0f0ff; border-radius: 8px;
                            padding: 16px; margin-bottom: 32px;
                            color: #333; font-size: 14px; line-height: 1.7;">
                    {report.summary.replace(chr(10), "<br>")}
                </div>

                <h2 style="color: #1a1a2e; font-size: 18px;
                           margin: 0 0 16px 0; border-bottom: 2px solid #4F46E5;
                           padding-bottom: 8px;">
                    Tendances clés
                </h2>
                <ul style="margin: 0 0 32px 0; padding-left: 20px;">
                    {trends_html}
                </ul>

                <h2 style="color: #1a1a2e; font-size: 18px;
                           margin: 0 0 16px 0; border-bottom: 2px solid #4F46E5;
                           padding-bottom: 8px;">
                    Articles analysés
                </h2>
                {articles_html}

            </div>

            <div style="background: #f8f9fa; padding: 20px; text-align: center;
                        border-top: 1px solid #eee;">
                <p style="margin: 0; color: #999; font-size: 12px;">
                    Email généré automatiquement par ton Agent IA
                    — Prochaine livraison dans 12 heures
                </p>
            </div>

        </div>
    </body>
    </html>
    """  # Fin de la construction du template HTML complet avec injection des variables

    return html  # Retourne la chaîne HTML complète


async def send_news_report(report: NewsReport) -> bool:
    """
    Envoie le rapport par email via Resend.
    Retourne True si l'envoi a réussi, False sinon.
    """
    try:  # Début du bloc de surveillance des erreurs
        init_resend()  # Appel de l'initialisation de la clé API

        email_to = os.getenv(
            "EMAIL_TO"
        )  # Récupération du destinataire depuis l'environnement
        if not email_to:  # Vérification du destinataire
            raise ValueError(
                "EMAIL_TO manquant dans .env"
            )  # Erreur si le destinataire est absent

        html_content = build_email_html(
            report
        )  # Appel de la fonction de création du HTML

        params = resend.Emails.SendParams(
            from_="Agent IA <onboarding@resend.dev>",  # Configuration de l'expéditeur (email par défaut Resend)
            to=[email_to],  # Configuration du destinataire
            subject=f"Rapport Tech IA — {report.generated_at}",  # Création de l'objet de l'email
            html=html_content,  # Injection du corps de l'email généré
        )  # Préparation des paramètres d'envoi

        email = resend.Emails.send(params)  # Exécution de l'envoi de l'email
        print(
            f"Email envoyé avec succès — ID : {email['id']}"
        )  # Notification de succès dans la console
        return True  # Retourne vrai en cas de succès

    except Exception as e:  # Capture de toute erreur survenue pendant le processus
        print(
            f"Erreur envoi email : {e}"
        )  # Affichage du message d'erreur dans la console
        return False  # Retourne faux en cas d'échec
