import asyncio
import httpx
from bs4 import BeautifulSoup

async def check_url(url):
    print(f"Checking {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, verify=False) as client:
        try:
            resp = await client.get(url)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("Successfully fetched!")
                soup = BeautifulSoup(resp.text, 'html.parser')
                title = soup.title.string if soup.title else "No title"
                print(f"Title: {title}")
                # Check for article links
                links = soup.find_all('a', href=True)
                print(f"Found {len(links)} links")
                for link in links[:5]:
                    print(f"Link: {link.get('href')}")
            else:
                print("Failed to fetch.")
        except Exception as e:
            print(f"Error: {e}")

async def main():
    urls = [
        "https://openai.com/zh-Hans-CN/research/index/?page=2",
        "https://openai.com/index", # New blog home
        "https://openai.com/news"
    ]
    for url in urls:
        await check_url(url)
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())

