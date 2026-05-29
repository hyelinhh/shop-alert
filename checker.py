import os
import json
import time
import requests
from bs4 import BeautifulSoup

# =============================================
#   여기만 수정하면 돼요!
# =============================================

# 크런치롤 스토어 검색 키워드 목록
CRUNCHYROLL_KEYWORDS = [
    "gintama",
    "ichibansho",
]

# =============================================
#   아래는 수정하지 않아도 돼요!
# =============================================

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


def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("seen", []))
    except Exception:
        return set()


def save_seen(seen_set):
    seen_list = list(seen_set)[-500:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen": seen_list}, f, ensure_ascii=False, indent=2)


def send_discord(title, url, price, image_url, source):
    if not DISCORD_WEBHOOK:
        print("[오류] DISCORD_WEBHOOK_URL 환경변수가 없습니다.")
        return

    embed = {
        "title": title[:250],
        "url": url,
        "color": 0xF47521,
        "fields": [
            {"name": "가격", "value": price if price else "가격 정보 없음", "inline": True},
            {"name": "출처", "value": source, "inline": True},
        ],
        "footer": {"text": "Shop Alert Bot"},
    }
    if image_url:
        embed["thumbnail"] = {"url": image_url}

    payload = {
        "content": "@here 🎉 새 상품 발견!",
        "embeds": [embed],
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        if resp.status_code == 204:
            print(f"  ✅ 알림 전송 성공: {title}")
        else:
            print(f"  ❌ 알림 전송 실패 ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"  ❌ Discord 오류: {e}")


def check_crunchyroll(keyword, seen_ids):
    search_url = (
        f"https://store.crunchyroll.com/search?q={requests.utils.quote(keyword)}"
        f"&sort=newest"
    )
    print(f"\n[Crunchyroll] '{keyword}' 검색 중...")

    try:
        time.sleep(2)
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        print(f"  상태코드: {resp.status_code}")
    except Exception as e:
        print(f"  요청 실패: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select(".product-tile, [class*='product-tile'], [class*='product-item']")
    if not items:
        items = soup.select("article[class*='product'], div[class*='ProductCard']")
    print(f"  발견된 상품 수: {len(items)}")

    new_items = []
    for i, item in enumerate(items[:15]):
        print(f"  [디버그] {i+1}번째 상품 처리 중...")

        # 제목
        title_tag = item.select_one(
            ".product-name, .pdp-link a, [class*='product-name'], h2, h3"
        )
        if not title_tag:
            print(f"  [디버그] {i+1}번째 - 제목 없음, 건너뜀")
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            print(f"  [디버그] {i+1}번째 - 제목 비어있음, 건너뜀")
            continue
        print(f"  [디버그] 제목: {title}")

        # URL
        link_tag = item.select_one("a[href]")
        if link_tag:
            href = link_tag.get("href", "")
            product_url = (
                href if href.startswith("http")
                else "https://store.crunchyroll.com" + href
            )
        else:
            product_url = search_url

        # 가격
        price_tag = item.select_one(".price, .sales .value, [class*='price']")
        price = price_tag.get_text(strip=True) if price_tag else None

        # 이미지
        img_tag = item.select_one("img")
        image_url = img_tag.get("src") or img_tag.get("data-src") if img_tag else None

        # 고유 ID는 제목 기반으로 (URL이 중복될 수 있어서)
        unique_id = f"cr_{title}"
        print(f"  [디버그] unique_id: {unique_id}")
        print(f"  [디버그] seen에 있나요? {unique_id in seen_ids}")

        if unique_id not in seen_ids:
            print(f"  [디버그] ✅ 새 상품으로 추가!")
            new_items.append({
                "id": unique_id,
                "title": title,
                "url": product_url,
                "price": price,
                "image": image_url,
                "source": "Crunchyroll Store",
            })
        else:
            print(f"  [디버그] 이미 본 상품, 건너뜀")

    return new_items


def main():
    print("=" * 50)
    print("Shop Alert Bot 시작!")
    print("=" * 50)

    seen_ids = load_seen()
    print(f"기존에 기록된 상품 수: {len(seen_ids)}")

    all_new_items = []

    for keyword in CRUNCHYROLL_KEYWORDS:
        new = check_crunchyroll(keyword, seen_ids)
        all_new_items.extend(new)
        time.sleep(3)

    print(f"\n새로 발견된 상품 총 {len(all_new_items)}개")

    for item in all_new_items:
        print(f"  → 알림 전송: {item['title']}")
        send_discord(
            title=item["title"],
            url=item["url"],
            price=item["price"],
            image_url=item["image"],
            source=item["source"],
        )
        seen_ids.add(item["id"])
        time.sleep(1)

    save_seen(seen_ids)
    print("\n완료! seen.json 저장됨.")


if __name__ == "__main__":
    main()
