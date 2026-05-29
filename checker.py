import os
import json
import time
import requests
from bs4 import BeautifulSoup

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
SEEN_FILE = "seen.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def main():
    keyword = "gintama"
    search_url = f"https://store.crunchyroll.com/search?q={requests.utils.quote(keyword)}&sort=newest"
    
    resp = requests.get(search_url, headers=HEADERS, timeout=15)
    print(f"상태코드: {resp.status_code}")
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # 첫번째 product-tile의 전체 HTML 출력
    tiles = soup.select(".product-tile, [class*='product-tile']")
    if tiles:
        print(f"타일 수: {len(tiles)}")
        print("=== 첫번째 타일 전체 HTML ===")
        print(str(tiles[0])[:1000])
    else:
        print("타일 없음")
        print("=== 전체 HTML 앞부분 ===")
        print(resp.text[:3000])

if __name__ == "__main__":
    main()
