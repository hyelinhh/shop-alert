import os
import json
import time
import schedule
import requests
from bs4 import BeautifulSoup

# =============================================
#   여기만 수정하면 돼요!
# =============================================

CRUNCHYROLL_KEYWORDS = [
    "gintama",
    "ichibansho",
]

CHECK_INTERVAL_MINUTES = 5  # 몇 분마다 체크할지

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
    items = soup.select("div.product-tile[data-pid]")
    print(f"  발견된 상품 수: {len(items)}")

    new_items = []
    for item in items[:20]:
        pid = item.get("data-pid", "").strip()
        if not pid:
            continue

        a_tag = item.find("a", attrs={"aria-label": True})
        if not a_tag:
            continue
        title = a_tag["aria-label"].replace("View image for ", "").strip()
        if not title:
            continue

        href = a_tag.get("href", "")
        product_url = (
            href if href.startswith("http")
            else "https://store.crunchyroll.com" + href
        )

        price_tag = item.select_one(".price .sales .value, [class*='price'] .value, .price")
        price = price_tag.get_text(strip=True) if price_tag else None

        img_tag = item.select_one("img")
        image_url = None
        if img_tag:
            image_url = img_tag.get("src") or img_tag.get("data-src")

        unique_id = f"cr_{pid}"
        if unique_id not in seen_ids:
            print(f"  ✅ 새 상품: {title}")
            new_items.append({
                "id": unique_id,
                "title": title,
                "url": product_url,
                "price": price,
                "image": image_url,
                "source": "Crunchyroll Store",
            })

    return new_items


def job():
    print("\n" + "=" * 50)
    print(f"체크 시작! ({time.strftime('%Y-%m-%d %H:%M:%S')})")
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
    print("완료! seen.json 저장됨.")


if __name__ == "__main__":
    print(f"Shop Alert Bot 시작! {CHECK_INTERVAL_MINUTES}분마다 체크합니다.")
    job()  # 시작하자마자 한 번 즉시 실행
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(30)
