from ddgs import DDGS
try:
    with DDGS() as ddgs:
        results = ddgs.text('Jev LLM', max_results=15)
        for r in results:
            print(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}\n{'-'*40}")
        print("Done searching Jev LLM")
except Exception as e:
    print(f'Error: {e}')
