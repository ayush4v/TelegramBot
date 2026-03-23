import asyncio
import aiohttp
from bs4 import BeautifulSoup
import urllib.parse

async def test_search():
    # Trying with a simpler query first
    query = "JEE Mains 2023 question paper download"
    search_url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(search_url, headers=headers, timeout=10) as response:
                print(f"Status for simple query: {response.status}")
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    results = soup.find_all('a', class_='result__a')
                    print(f"Found {len(results)} results for simple query")
                
                # Testing with filetype:pdf
                query2 = "JEE Mains 2023 filetype:pdf"
                url2 = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query2)}"
                async with session.get(url2, headers=headers, timeout=10) as response2:
                    print(f"Status for filetype query: {response2.status}")
                    if response2.status == 200:
                        html2 = await response2.text()
                        soup2 = BeautifulSoup(html2, 'lxml')
                        results2 = soup2.find_all('a', class_='result__a')
                        print(f"Found {len(results2)} results for filetype query")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
