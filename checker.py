import os
import json
import time
import requests
from bs4 import BeautifulSoup

# =============================================
#   여기만 수정하면 돼요!
# =============================================

# 아마존 브랜드 스토어 URL 목록 (여러 개 추가 가능)
AMAZON_STORES = [
    {
        "name": "Ichibansho Figure",
        "url": "https://www.amazon.com/stores/IchibanshoFigure/page/93313B13-32D0-4E42-9610-816E8765A855",
    },
]

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

    color_map = {
        "Ichibansho Figure (Amazon)": 0xFF9900,
        "Crunchyroll Store": 0xF47521,
    }
    color = color_map.get(source, 0xFF9900)

    embed = {
        "title": title[:250],
        "url": url,
        "color": color,
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


def check_amazon_store(store, seen_ids):
    """아마존 브랜드 스토어 페이지에서 새 상품 감지"""
    print(f"\n[Amazon Store] '{store['name']}' 확인 중...")

    try:
        time.sleep(2)
        resp = requests.get(store["url"], headers=HEADERS, timeout=15)
        print(f"  상태코드: {resp.status_code}")
    except Exception as e:
        print(f"  요청 실패: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # 아마존 브랜드 스토어 상품 카드 선택자 (여러 방식 시도)
    items = soup.select('[data-asin]')
    if not items:
        items = soup.select('.s-result-item[data-asin]')
    if not items:
        items = soup.select('[class*="ProductCard"], [class*="product-card"]')

    print(f"  발견된 상품 수: {len(items)}")

    # 상품을 못 찾은 경우 — 페이지 구조 디버그용 출력
    if not items:
        print("  ⚠️ 상품을 찾지 못했어요. 페이지 일부를 출력합니다:")
        print(resp.text[:2000])
        return []

    new_items = []
    source_name = f"{store['name']} (Amazon)"

    for item in items[:20]:
        asin = item.get("data-asin", "").strip()
        if not asin:
            continue

        # 제목
        title_tag = (
            item.select_one("h2 span")
            or item.select_one("[class*='title']")
            or item.select_one("span[class*='text']")
        )
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            continue

        # URL
        link_tag = item.select_one("a[href*='/dp/']") or item.select_one("a[href]")
        if link_tag:
            href = link_tag.get("href", "")
            product_url = (
                href if href.startswith("http")
                else "https://www.amazon.com" + href
            )
        else:
            product_url = f"https://www.amazon.com/dp/{asin}"

        # 가격
        price_tag = item.select_one(".a-price .a-offscreen")
        price = price_tag.get_text(strip=True) if price_tag else None

        # 이미지
        img_tag = item.select_one("img")
        image_url = img_tag.get("src") if img_tag else None

        unique_id = f"amzstore_{asin}"
        if unique_id not in seen_ids:
            new_items.append({
                "id": unique_id,
                "title": title,
                "url": product_url,
                "price": price,
                "image": image_url,
                "source": source_name,
            })

    return new_items


def check_crunchyroll(keyword, seen_ids):
    """크런치롤 스토어 검색"""
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
    for item in items[:15]:
        title_tag = item.select_one(
            ".product-name, .pdp-link a, [class*='product-name'], h2, h3"
        )
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            continue

        link_tag = item.select_one("a[href]")
        if link_tag:
            href = link_tag.get("href", "")
            product_url = (
                href if href.startswith("http")
                else "https://store.crunchyroll.com" + href
            )
        else:
            product_url = search_url

        price_tag = item.select_one(".price, .sales .value, [class*='price']")
        price = price_tag.get_text(strip=True) if price_tag else None

        img_tag = item.select_one("img")
        image_url = img_tag.get("src") or img_tag.get("data-src") if img_tag else None

        unique_id = f"cr_{product_url}"
        if unique_id not in seen_ids:
            new_items.append({
                "id": unique_id,
                "title": title,
                "url": product_url,
                "price": price,
                "image": image_url,
                "source": "Crunchyroll Store",
            })

    return new_items


def main():
    print("=" * 50)
    print("Shop Alert Bot 시작!")
    print("=" * 50)

    seen_ids = load_seen()
    print(f"기존에 기록된 상품 수: {len(seen_ids)}")

    all_new_items = []

    # 아마존 브랜드 스토어 체크
    for store in AMAZON_STORES:
        new = check_amazon_store(store, seen_ids)
        all_new_items.extend(new)
        time.sleep(3)

    # 크런치롤 체크
    for keyword in CRUNCHYROLL_KEYWORDS:
        new = check_crunchyroll(keyword, seen_ids)
        all_new_items.extend(new)
        time.sleep(3)

    print(f"\n새로 발견된 상품 총 {len(all_new_items)}개")

    for item in all_new_items:
        print(f"  → {item['title']}")
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
