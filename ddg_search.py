import requests
from bs4 import BeautifulSoup
import urllib.parse

def duckduckgo_search_pdfs(query: str, limit: int = 10) -> list:
    """Fallback search using DuckDuckGo (scraping) if Google is blocked."""
    url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query + ' filetype:pdf')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    results = []
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for a in soup.find_all('a', class_='result__a'):
                href = a.get('href')
                if href and ".pdf" in href.lower():
                    title = a.get_text().strip()
                    results.append({"title": title, "url": href})
                if len(results) >= limit:
                    break
    except Exception as e:
        print(f"DDG Search Error: {e}")
        
    return results

# Test it
if __name__ == "__main__":
    q = "JEE Main 2023 question paper"
    print(f"Searching for: {q}")
    res = duckduckgo_search_pdfs(q)
    for r in res:
        print(f"-> {r['title']}: {r['url']}")
