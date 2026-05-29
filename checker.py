import os
import json
import time
import requests
from bs4 import BeautifulSoup

# =============================================
#   여기만 수정하면 돼요!
# =============================================

# 아마존 검색 키워드 목록 (원하는 키워드 추가/삭제)
AMAZON_KEYWORDS = [
    "gintama",
    "ichibansho",
]

# 크런치롤 스토어 검색 키워드 목록
CRUNCHYROLL_KEYWORDS = [
    "gintama",
    "ichibansho",
]

# 가격 필터: 이 금액 이하 상품만 알림 (달러 기준, 없애려면 None으로)
MAX_PRICE = None  # 예: 50 이면 50달러 이하만 알림

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
    """이미 알림 보낸 상품 목록 불러오기"""
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("seen", []))
    except Exception:
        return set()


def save_seen(seen_set):
    """알림 보낸 상품 목록 저장하기"""
    # 너무 많아지면 최신 500개만 보관
    seen_list = list(seen_set)[-500:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen": seen_list}, f, ensure_ascii=False, indent=2)


def send_discord(title, url, price, image_url, source):
    """Discord로 알림 보내기"""
    if not DISCORD_WEBHOOK:
        print("[오류] DISCORD_WEBHOOK_URL 환경변수가 없습니다.")
        return

    color = 0xFF9900 if source == "Amazon" else 0xF47521  # 아마존=주황, 크런치롤=오렌지

    embed = {
        "title": title[:250],  # Discord 제목 최대 256자
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
        "content": "@here 새 상품 발견!",
        "embeds": [embed],
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        if resp.status_code == 204:
            print(f"[알림 전송 성공] {title}")
        else:
            print(f"[알림 전송 실패] 상태코드: {resp.status_code}, 내용: {resp.text}")
    except Exception as e:
        print(f"[Discord 전송 오류] {e}")


def check_amazon(keyword, seen_ids):
    """아마존에서 키워드 검색 후 새 상품 찾기"""
    search_url = (
        f"https://www.amazon.com/s?k={requests.utils.quote(keyword)}"
        "&s=date-desc-rank"  # 최신순 정렬
    )
    print(f"\n[Amazon] '{keyword}' 검색 중... URL: {search_url}")

    try:
        time.sleep(2)  # 서버 부하 방지
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        print(f"[Amazon] 응답 상태코드: {resp.status_code}")
    except Exception as e:
        print(f"[Amazon] 요청 실패: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select('[data-component-type="s-search-result"]')
    print(f"[Amazon] 발견된 상품 수: {len(items)}")

    new_items = []
    for item in items[:10]:  # 상위 10개만 확인
        asin = item.get("data-asin", "").strip()
        if not asin:
            continue

        # 제목
        title_tag = item.select_one("h2 .a-link-normal span")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        # URL
        link_tag = item.select_one("h2 .a-link-normal")
        product_url = (
            "https://www.amazon.com" + link_tag["href"]
            if link_tag and link_tag.get("href")
            else search_url
        )

        # 가격
        price_tag = item.select_one(".a-price .a-offscreen")
        price = price_tag.get_text(strip=True) if price_tag else None

        # 가격 필터
        if MAX_PRICE and price:
            try:
                price_num = float(price.replace("$", "").replace(",", "").strip())
                if price_num > MAX_PRICE:
                    continue
            except Exception:
                pass

        # 이미지
        img_tag = item.select_one("img.s-image")
        image_url = img_tag["src"] if img_tag else None

        unique_id = f"amazon_{asin}"
        if unique_id not in seen_ids:
            new_items.append(
                {
                    "id": unique_id,
                    "title": title,
                    "url": product_url,
                    "price": price,
                    "image": image_url,
                    "source": "Amazon",
                }
            )

    return new_items


def check_crunchyroll(keyword, seen_ids):
    """크런치롤 스토어에서 키워드 검색 후 새 상품 찾기"""
    search_url = (
        f"https://store.crunchyroll.com/search?q={requests.utils.quote(keyword)}"
        "&sort=newest"
    )
    print(f"\n[Crunchyroll] '{keyword}' 검색 중... URL: {search_url}")

    try:
        time.sleep(2)
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        print(f"[Crunchyroll] 응답 상태코드: {resp.status_code}")
    except Exception as e:
        print(f"[Crunchyroll] 요청 실패: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # 크런치롤 스토어 상품 카드 선택자
    items = soup.select(".product-tile, .product-grid-tile, [class*='product-tile']")
    print(f"[Crunchyroll] 발견된 상품 수: {len(items)}")

    # 선택자로 못 찾을 때 대안 시도
    if not items:
        items = soup.select("article[class*='product'], div[class*='product-item']")
        print(f"[Crunchyroll] 대안 선택자로 재시도: {len(items)}개")

    new_items = []
    for item in items[:10]:
        # 제목
        title_tag = item.select_one(
            ".product-name, .pdp-link a, [class*='product-name'], h2, h3"
        )
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            continue

        # URL
        link_tag = item.select_one("a[href]")
        if link_tag:
            href = link_tag.get("href", "")
            product_url = (
                href if href.startswith("http") else "https://store.crunchyroll.com" + href
            )
        else:
            product_url = search_url

        # 가격
        price_tag = item.select_one(".price, .sales .value, [class*='price']")
        price = price_tag.get_text(strip=True) if price_tag else None

        # 이미지
        img_tag = item.select_one("img")
        image_url = img_tag.get("src") or img_tag.get("data-src") if img_tag else None

        # 고유 ID 생성 (URL 기반)
        unique_id = f"cr_{product_url}"
        if unique_id not in seen_ids:
            new_items.append(
                {
                    "id": unique_id,
                    "title": title,
                    "url": product_url,
                    "price": price,
                    "image": image_url,
                    "source": "Crunchyroll Store",
                }
            )

    return new_items


def main():
    print("=" * 50)
    print("Shop Alert Bot 시작!")
    print("=" * 50)

    seen_ids = load_seen()
    print(f"이미 알림 보낸 상품 수: {len(seen_ids)}")

    all_new_items = []

    # 아마존 체크
    for keyword in AMAZON_KEYWORDS:
        new = check_amazon(keyword, seen_ids)
        all_new_items.extend(new)
        time.sleep(3)  # 키워드 사이 대기

    # 크런치롤 체크
    for keyword in CRUNCHYROLL_KEYWORDS:
        new = check_crunchyroll(keyword, seen_ids)
        all_new_items.extend(new)
        time.sleep(3)

    print(f"\n새로 발견된 상품 총 {len(all_new_items)}개")

    # 알림 전송 & seen에 추가
    for item in all_new_items:
        print(f"  -> 알림 전송: {item['title']}")
        send_discord(
            title=item["title"],
            url=item["url"],
            price=item["price"],
            image_url=item["image"],
            source=item["source"],
        )
        seen_ids.add(item["id"])
        time.sleep(1)  # Discord 속도 제한 방지

    save_seen(seen_ids)
    print("\n완료! seen.json 저장됨.")


if __name__ == "__main__":
    main()
