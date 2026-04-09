import httpx
from bs4 import BeautifulSoup
from typing import List
from schemas.news_schema import NewsArticle
import asyncio


# Headers pour se faire passer pour un vrai navigateur
# Sans ça, certains sites bloquent les requêtes automatiques
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Sites à ignorer — paywalls ou sites qui bloquent systématiquement
BLOCKED_DOMAINS = [
    "medium.com",
    "wsj.com",
    "nytimes.com",
    "ft.com",
    "bloomberg.com",
]


async def search_duckduckgo(query: str, max_results: int = 5) -> List[dict]:
    """
    Cherche sur DuckDuckGo et retourne les résultats.
    DuckDuckGo est gratuit, sans clé API, et respectueux de la vie privée.
    """
    print(f"Recherche DuckDuckGo : {query}")

    # URL de recherche DuckDuckGo
    search_url = "https://html.duckduckgo.com/html/"

    results = []

    try:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=15.0, follow_redirects=True
        ) as client:
            response = await client.post(search_url, data={"q": query, "kl": "fr-fr"})

            if response.status_code != 200:
                print(f"DuckDuckGo a répondu avec le code : {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            # Les résultats sont dans des divs avec la classe "result"
            result_divs = soup.find_all("div", class_="result", limit=max_results + 3)

            for div in result_divs:
                if len(results) >= max_results:
                    break

                # Extraire le titre et l'URL
                title_tag = div.find("a", class_="result__a")
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                url = title_tag.get("href", "")

                # Filtrer les URLs vides ou les domaines bloqués
                if not url or not url.startswith("http"):
                    continue

                if any(domain in url for domain in BLOCKED_DOMAINS):
                    print(f"  Domaine ignoré : {url}")
                    continue

                results.append(
                    {
                        "title": title,
                        "url": url,
                    }
                )
                print(f"  Résultat trouvé : {title[:60]}...")

    except Exception as e:
        print(f"Erreur lors de la recherche DuckDuckGo : {e}")

    print(f"Total résultats trouvés : {len(results)}")
    return results


async def scrape_article(url: str, title: str) -> NewsArticle | None:
    """
    Télécharge et extrait le contenu textuel d'une URL.
    Retourne None si le scraping échoue.
    """
    print(f"  Scraping : {url[:70]}...")

    try:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=10.0, follow_redirects=True
        ) as client:
            response = await client.get(url)

            if response.status_code != 200:
                print(f"  Echec — code HTTP : {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Supprimer les éléments inutiles : navigation, pubs, footer
            for tag in soup(
                [
                    "script",
                    "style",
                    "nav",
                    "header",
                    "footer",
                    "aside",
                    "form",
                    "button",
                    "iframe",
                    "noscript",
                    "ads",
                ]
            ):
                tag.decompose()

            # Essayer de trouver le contenu principal de l'article
            # Les sites utilisent différentes balises selon leur structure
            content = ""

            # Priorité 1 — balise article
            article_tag = soup.find("article")
            if article_tag:
                content = article_tag.get_text(separator=" ", strip=True)

            # Priorité 2 — balise main
            if not content or len(content) < 100:
                main_tag = soup.find("main")
                if main_tag:
                    content = main_tag.get_text(separator=" ", strip=True)

            # Priorité 3 — tous les paragraphes
            if not content or len(content) < 100:
                paragraphs = soup.find_all("p")
                content = " ".join([p.get_text(strip=True) for p in paragraphs])

            # Nettoyage final
            content = " ".join(content.split())  # Supprime les espaces multiples

            if len(content) < 50:
                print(f"  Contenu trop court ({len(content)} caractères) — ignoré")
                return None

            # On limite à 3000 caractères par article pour ne pas surcharger Gemini
            content = content[:3000]

            # Extraire le nom du domaine comme source
            from urllib.parse import urlparse

            source = urlparse(url).netloc.replace("www.", "")

            print(f"  OK — {len(content)} caractères extraits depuis {source}")

            return NewsArticle(
                title=title,
                url=url,
                content=content,
                source=source,
            )

    except httpx.TimeoutException:
        print(f"  Timeout — site trop lent")
        return None
    except Exception as e:
        print(f"  Erreur scraping : {e}")
        return None


async def scrape_tech_news(max_articles: int = 5) -> List[NewsArticle]:
    """
    Fonction principale — cherche et scrape les actualités tech.
    Retourne une liste d'articles avec leur contenu.
    """
    print("\n--- Démarrage du scraping des actus tech ---")

    # Requêtes de recherche pour avoir des résultats variés
    queries = [
        "actualités intelligence artificielle aujourd'hui",
        "tech news innovation numérique",
        "nouvelles technologies startups",
    ]

    all_search_results = []

    # On cherche avec chaque requête
    for query in queries:
        results = await search_duckduckgo(query, max_results=3)
        all_search_results.extend(results)
        # Petite pause pour ne pas surcharger DuckDuckGo
        await asyncio.sleep(1)

    # Déduplique les URLs
    seen_urls = set()
    unique_results = []
    for result in all_search_results:
        if result["url"] not in seen_urls:
            seen_urls.add(result["url"])
            unique_results.append(result)

    print(f"\n{len(unique_results)} URLs uniques à scraper")

    # Scraping de chaque article
    articles = []
    for result in unique_results[: max_articles + 3]:
        if len(articles) >= max_articles:
            break

        article = await scrape_article(result["url"], result["title"])
        if article:
            articles.append(article)

        # Pause entre chaque scraping pour être respectueux des serveurs
        await asyncio.sleep(0.5)

    print(f"\n{len(articles)} articles scrapés avec succès")
    print("--- Fin du scraping ---\n")

    return articles
