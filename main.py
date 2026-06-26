from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://snkrdunk.com",
}

# カードIDマッピング（スニーカーダンクの商品ID）
CARD_MAP = {
    "ミュウツーV SR": {"id": "91133", "name": "ミュウツーV SR SA[S10b 074/071]"},
    "ブラッキー☆": {"id": "91160", "name": "ブラッキー☆ プロモ[S8a-P 012/025]"},
}

@app.get("/")
def root():
    return {"status": "ok", "message": "PSA SOLD Tracker API"}

@app.get("/sold/{card_key}")
async def get_sold(card_key: str, grade: int = 10):
    """
    スニーカーダンクからSOLD価格を取得
    """
    if card_key not in CARD_MAP:
        return {"error": "カードが見つかりません", "available": list(CARD_MAP.keys())}

    card = CARD_MAP[card_key]
    url = f"https://snkrdunk.com/apparels/{card['id']}/used"

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
            res = await client.get(url)
            res.raise_for_status()
    except Exception as e:
        return {"error": f"取得失敗: {str(e)}"}

    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.select("[class*='item'], [class*='product'], [class*='card']")

    sold_prices = []
    for item in items:
        # SOLDバッジの確認
        text = item.get_text()
        is_sold = "SOLD" in text or "売り切れ" in text

        # PSAグレードの確認
        grade_match = re.search(rf"PSA\s*{grade}(?!\d)", text)
        if not grade_match:
            continue

        # 価格抽出
        price_match = re.search(r"([\d,]+)\s*(?:円|¥)?", text)
        if price_match:
            price = int(price_match.group(1).replace(",", ""))
            if price > 1000:  # 最低価格フィルタ
                sold_prices.append({
                    "price": price,
                    "sold": is_sold,
                    "scraped_at": datetime.now().isoformat(),
                })

    # 直近8件のSOLD価格を返す
    sold_only = [p for p in sold_prices if p["sold"]]
    recent = sold_only[-8:] if len(sold_only) >= 8 else sold_only

    if not recent:
        return {
            "card": card_key,
            "grade": grade,
            "sold_count": 0,
            "prices": [],
            "latest_price": None,
            "note": "SOLDデータが見つかりませんでした。セレクタを調整してください。"
        }

    prices = [r["price"] for r in recent]
    return {
        "card": card_key,
        "grade": grade,
        "sold_count": len(prices),
        "prices": prices,
        "latest_price": prices[-1],
        "avg_price": int(sum(prices) / len(prices)),
        "scraped_at": datetime.now().isoformat(),
    }

@app.get("/cards")
def list_cards():
    return {"cards": list(CARD_MAP.keys())}
