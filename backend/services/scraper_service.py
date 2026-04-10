import httpx
from bs4 import BeautifulSoup
from typing import List
from schemas.news_schema import NewsArticle
import asyncio
from duckduckgo_search import DDGS  # <--- On utilise la lib officielle
from urllib.parse import urlparse

# Headers pour le scraping des articles (pas pour la recherche)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

BLOCKED_DOMAINS = ["medium.com", "wsj.com", "nytimes.com", "ft.com", "bloomberg.com"]


async def search_duckduckgo(query: str, max_results: int = 5) -> List[dict]:
    """
    Utilise la bibliothèque duckduckgo_search pour éviter les codes 202.
    """
    print(f"Recherche DuckDuckGo : {query}")
    results = []

    try:
        # DDGS est beaucoup plus robuste que le scraping manuel du HTML
        with DDGS() as ddgs:
            # On demande un peu plus pour filtrer les domaines bloqués ensuite
            ddgs_gen = ddgs.text(query, region="fr-fr", safesearch="off", timelimit="d")

            for r in ddgs_gen:
                if len(results) >= max_results:
                    break

                url = r.get("href", "")
                title = r.get("title", "")

                # Filtrage
                if not url or any(domain in url for domain in BLOCKED_DOMAINS):
                    continue

                results.append({"title": title, "url": url})
                print(f"  Résultat trouvé : {title[:60]}...")

    except Exception as e:
        print(f"Erreur lors de la recherche DuckDuckGo : {e}")

    print(f"Total résultats trouvés : {len(results)}")
    return results


async def scrape_article(url: str, title: str) -> NewsArticle | None:
    """
    Télécharge et extrait le contenu textuel d'une URL.
    """
    print(f"  Scraping : {url[:70]}...")

    try:
        # Utilisation de follow_redirects pour éviter les erreurs sur les liens raccourcis
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=15.0, follow_redirects=True
        ) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Nettoyage
            for tag in soup(
                ["script", "style", "nav", "header", "footer", "aside", "form", "ads"]
            ):
                tag.decompose()

            # Extraction (Priorité : Article > Main > Paragraphs)
            target = soup.find("article") or soup.find("main")
            if target:
                content = target.get_text(separator=" ", strip=True)
            else:
                content = " ".join([p.get_text(strip=True) for p in soup.find_all("p")])

            content = " ".join(content.split())  # Normalise les espaces

            if len(content) < 200:  # On monte un peu le seuil pour avoir de la qualité
                return None

            source = urlparse(url).netloc.replace("www.", "")
            print(f"  OK — {len(content[:3000])} caractères extraits depuis {source}")

            return NewsArticle(
                title=title,
                url=url,
                content=content[:3000],
                source=source,
            )
    except Exception as e:
        print(f"  Erreur scraping {url}: {e}")
        return None


async def scrape_tech_news(max_articles: int = 5) -> List[NewsArticle]:
    """
    Fonction principale.
    """
    print("\n--- Démarrage du scraping des actus tech ---")
    queries = [
        "actualités intelligence artificielle",
        "innovation numérique france",
        "tech startups news",
    ]

    all_results = []
    for query in queries:
        res = await search_duckduckgo(query, max_results=3)
        all_results.extend(res)
        await asyncio.sleep(1.5)  # Un peu plus de repos pour l'IP

    # Déduplication
    unique_results = {r["url"]: r for r in all_results}.values()

    articles = []
    for res in list(unique_results)[: max_articles + 2]:
        if len(articles) >= max_articles:
            break

        article = await scrape_article(res["url"], res["title"])
        if article:
            articles.append(article)
        await asyncio.sleep(1)

    print(f"\n{len(articles)} articles collectés.")
    return articles
