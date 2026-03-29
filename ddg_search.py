import primp
from bs4 import BeautifulSoup
import urllib.parse
import asyncio
import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

async def duckduckgo_search_pdfs(query: str, limit: int = 10) -> list:
    """Resilient search using primp to bypass cloud blocking."""
    encoded_q = urllib.parse.quote(f"{query} filetype:pdf")
    url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
    
    results = []
    try:
        async with primp.AsyncClient(impersonate="chrome_123") as client:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = await client.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for a in soup.select('a.result__a'):
                    href = a.get('href')
                    # Handle DDG internal redirects
                    if 'uddg=' in href:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = urllib.parse.unquote(parsed.get('uddg', [''])[0])
                    
                    title = a.get_text().strip()
                    results.append({"title": title, "url": href})
                    
                    if len(results) >= limit:
                        break
            else:
                print(f"Search failed with status: {response.status_code}")
    except Exception as e:
        print(f"DDG Search Error: {e}")
        
    return results

# Test it
if __name__ == "__main__":
    q = "JEE Main 2023 question paper"
    print(f"Searching for: {q}")
    res = asyncio.run(duckduckgo_search_pdfs(q))
    for r in res:
        print(f"-> {r['title']}: {r['url']}")
