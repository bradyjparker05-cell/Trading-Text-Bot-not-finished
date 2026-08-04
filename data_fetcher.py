import json
import urllib.request

import yfinance as yf

TICKERS = {
    "VOO": "Vanguard S&P 500 ETF",
    "QQQM": "Invesco Nasdaq 100 ETF",
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "SPY": "SPDR S&P 500 ETF",
}


def fetch_stock_data():
    data = {}
    for ticker, name in TICKERS.items():
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")

        if hist.empty:
            data[ticker] = {"name": name, "price": None, "change_pct": None, "news": []}
            continue

        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_close
        change_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close else 0.0

        news_items = []
        try:
            for item in t.news[:3]:
                content = item.get("content", item)
                title = content.get("title") or item.get("title")
                link = (content.get("clickThroughUrl") or {}).get("url") or item.get("link")
                if title and link:
                    news_items.append({"title": title, "link": link})
        except Exception:
            pass

        data[ticker] = {
            "name": name,
            "price": round(last_close, 2),
            "change_pct": round(change_pct, 2),
            "news": news_items,
        }

    return data


def fetch_macro_data():
    macro = {"vix": None, "treasury_10y": None}

    try:
        vix_hist = yf.Ticker("^VIX").history(period="1d")
        if not vix_hist.empty:
            macro["vix"] = round(float(vix_hist["Close"].iloc[-1]), 2)
    except Exception:
        pass

    try:
        tnx_hist = yf.Ticker("^TNX").history(period="1d")
        if not tnx_hist.empty:
            macro["treasury_10y"] = round(float(tnx_hist["Close"].iloc[-1]) / 10, 2)
    except Exception:
        pass

    return macro


def fetch_fear_greed():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
        fg = payload.get("fear_and_greed", {})
        score = fg.get("score")
        rating = fg.get("rating")
        if score is not None:
            return {"score": round(float(score)), "rating": rating}
    except Exception:
        pass

    return {"score": None, "rating": None}


def fetch_reddit_sentiment(limit=5):
    url = f"https://www.reddit.com/r/wallstreetbets/hot.json?limit={limit}"
    headers = {"User-Agent": "market-newsletter-bot/1.0"}
    posts = []

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
        for child in payload.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = post.get("title")
            permalink = post.get("permalink")
            score = post.get("score")
            if title and permalink:
                posts.append({
                    "title": title,
                    "link": f"https://www.reddit.com{permalink}",
                    "score": score,
                })
    except Exception:
        pass

    return posts


def fetch_all():
    return {
        "stocks": fetch_stock_data(),
        "macro": fetch_macro_data(),
        "fear_greed": fetch_fear_greed(),
        "reddit": fetch_reddit_sentiment(),
    }
