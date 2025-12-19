import asyncio
import httpx
from bs4 import BeautifulSoup

async def check_openai():
    url = "https://openai.com/zh-Hans-CN/research/index/?page=2"
    print(f"Checking {url}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("Success! First 500 chars:")
                print(resp.text[:500])
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Try to find articles
                articles = soup.find_all(['article', 'div'], class_=lambda x: x and ('post' in str(x).lower() or 'card' in str(x).lower() or 'item' in str(x).lower()))
                print(f"Found {len(articles)} potential article elements (generic)")
                
                # Check for specific structure
                links = soup.find_all('a', href=True)
                research_links = [l.get('href') for l in links if '/research/' in l.get('href')]
                print(f"Found {len(research_links)} research links")
                for l in research_links[:5]:
                    print(f"  - {l}")
            else:
                print("Failed.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_openai())

