from googlesearch import search

query = "JEE Main Advanced Previous Year Papers PDF with solutions"
print(f"Testing query: {query}")
results = []
try:
    for url in search(query, num_results=10):
        print(f"Found: {url}")
        results.append(url)
except Exception as e:
    print(f"Error: {e}")

if not results:
    print("No results found!")
else:
    print(f"Found {len(results)} results.")
