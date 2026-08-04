import json
import os
import re
import urllib.request

import yfinance as yf

TICKERS = {
    "VOO": "Vanguard S&P 500 ETF",
    "QQQM": "Invesco Nasdaq 100 ETF",
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "SPY": "SPDR S&P 500 ETF",
}

SUBREDDITS = ["wallstreetbets", "stocks", "investing"]

CONGRESS_FEEDS = [
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json",
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _sma(closes, period):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def fetch_stocktwits_sentiment(ticker):
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    bullish, bearish = 0, 0
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
        for msg in payload.get("messages", []):
            sentiment = (msg.get("entities", {}) or {}).get("sentiment") or {}
            basic = sentiment.get("basic")
            if basic == "Bullish":
                bullish += 1
            elif basic == "Bearish":
                bearish += 1
    except Exception:
        pass
    return {"bullish": bullish, "bearish": bearish}


def fetch_reddit_mentions(tickers, posts_per_sub=25):
    mention_counts = {t: 0 for t in tickers}
    pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in tickers) + r")\b")

    for sub in SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit={posts_per_sub}"
        headers = {**BROWSER_HEADERS, "User-Agent": "market-newsletter-bot/1.0"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode())
            for child in payload.get("data", {}).get("children", []):
                title = (child.get("data", {}) or {}).get("title", "")
                for match in pattern.findall(title.upper()):
                    mention_counts[match] += 1
        except Exception:
            continue

    return mention_counts


def fetch_reddit_top_posts(limit=5):
    url = f"https://www.reddit.com/r/wallstreetbets/hot.json?limit={limit}"
    headers = {**BROWSER_HEADERS, "User-Agent": "market-newsletter-bot/1.0"}
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


def fetch_congress_trades(tickers, days=45):
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=days)
    counts = {t: {"buys": 0, "sells": 0} for t in tickers}

    for url in CONGRESS_FEEDS:
        try:
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                records = json.loads(resp.read().decode())
        except Exception:
            continue

        for rec in records:
            ticker = (rec.get("ticker") or "").strip().upper()
            if ticker not in tickers:
                continue

            date_str = rec.get("transaction_date") or rec.get("disclosure_date") or ""
            parsed = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None or parsed < cutoff:
                continue

            tx_type = (rec.get("type") or rec.get("transaction_type") or "").lower()
            if "purchase" in tx_type or "buy" in tx_type:
                counts[ticker]["buys"] += 1
            elif "sale" in tx_type or "sell" in tx_type:
                counts[ticker]["sells"] += 1

    return counts


def compute_signal(closes, volumes, reddit_mentions, stocktwits, analyst_consensus=None, congress=None):
    votes = []
    reasons = []

    rsi = _rsi(closes)
    if rsi is not None:
        if rsi >= 70:
            votes.append(-1)
            reasons.append(f"RSI {rsi} (overbought)")
        elif rsi <= 30:
            votes.append(1)
            reasons.append(f"RSI {rsi} (oversold)")
        else:
            votes.append(0)
            reasons.append(f"RSI {rsi} (neutral)")

    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    if sma20 and sma50:
        if closes[-1] > sma20 > sma50:
            votes.append(1)
            reasons.append("price above 20/50-day MA (uptrend)")
        elif closes[-1] < sma20 < sma50:
            votes.append(-1)
            reasons.append("price below 20/50-day MA (downtrend)")
        else:
            votes.append(0)
            reasons.append("mixed moving average trend")

    if len(closes) >= 6:
        momentum = ((closes[-1] - closes[-6]) / closes[-6]) * 100
        if momentum > 2:
            votes.append(1)
        elif momentum < -2:
            votes.append(-1)
        else:
            votes.append(0)
        reasons.append(f"momentum {momentum:+.1f}% over 5 days")

    if len(volumes) >= 20 and volumes[-1]:
        avg_vol = sum(volumes[-20:]) / 20
        vol_ratio = volumes[-1] / avg_vol if avg_vol else 1
        if vol_ratio > 1.5:
            votes.append(1 if votes and sum(votes) >= 0 else -1)
            reasons.append(f"volume {vol_ratio:.1f}x average")

    bullish, bearish = stocktwits.get("bullish", 0), stocktwits.get("bearish", 0)
    if bullish + bearish >= 5:
        ratio = bullish / (bullish + bearish)
        if ratio > 0.6:
            votes.append(1)
            reasons.append(f"StockTwits {ratio:.0%} bullish")
        elif ratio < 0.4:
            votes.append(-1)
            reasons.append(f"StockTwits {ratio:.0%} bullish")

    if reddit_mentions >= 3:
        votes.append(1)
        reasons.append(f"{reddit_mentions} Reddit mentions today")

    if analyst_consensus:
        buy_total = analyst_consensus.get("strong_buy", 0) + analyst_consensus.get("buy", 0)
        sell_total = analyst_consensus.get("sell", 0) + analyst_consensus.get("strong_sell", 0)
        hold_total = analyst_consensus.get("hold", 0)
        total = buy_total + sell_total + hold_total
        if total >= 5:
            ratio = buy_total / total
            if ratio > 0.6:
                votes.extend([1, 1])
                reasons.append(f"Wall Street {ratio:.0%} buy-rated ({total} analysts)")
            elif ratio < 0.4:
                votes.extend([-1, -1])
                reasons.append(f"Wall Street {ratio:.0%} buy-rated ({total} analysts)")
            else:
                votes.extend([0, 0])
                reasons.append(f"Wall Street split {ratio:.0%} buy-rated ({total} analysts)")

    if congress:
        buys, sells = congress.get("buys", 0), congress.get("sells", 0)
        net = buys - sells
        if buys + sells >= 2:
            if net > 0:
                votes.append(1)
                reasons.append(f"Congress: {buys} buys vs {sells} sells (last 45 days)")
            elif net < 0:
                votes.append(-1)
                reasons.append(f"Congress: {buys} buys vs {sells} sells (last 45 days)")

    if not votes:
        return {"score": 50, "signal": "HOLD", "confidence": 0, "reasoning": "Not enough data."}

    avg_vote = sum(votes) / len(votes)
    score = round(50 + avg_vote * 50)
    score = max(0, min(100, score))

    if score >= 65:
        signal = "BUY"
    elif score <= 35:
        signal = "REDUCE"
    else:
        signal = "HOLD"

    agreeing = sum(1 for v in votes if (v > 0) == (avg_vote > 0) or v == 0)
    confidence = round((agreeing / len(votes)) * 100)

    if rsi is not None and rsi >= 75 and signal == "BUY":
        signal = "HOLD"
        reasons.append("⚠ overbought — trend is strong but chasing here is risky")
    elif rsi is not None and rsi <= 25 and signal == "REDUCE":
        signal = "HOLD"
        reasons.append("⚠ oversold — trend is weak but may already reflect bad news")

    return {
        "score": score,
        "signal": signal,
        "confidence": confidence,
        "reasoning": "; ".join(reasons),
    }


def fetch_analyst_consensus(ticker):
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        return None

    url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={ticker}&token={api_key}"
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
        if not payload:
            return None
        latest = payload[0]
        return {
            "period": latest.get("period"),
            "strong_buy": latest.get("strongBuy", 0),
            "buy": latest.get("buy", 0),
            "hold": latest.get("hold", 0),
            "sell": latest.get("sell", 0),
            "strong_sell": latest.get("strongSell", 0),
        }
    except Exception:
        return None


def fetch_stock_data():
    data = {}
    reddit_mentions = fetch_reddit_mentions(list(TICKERS.keys()))
    congress_trades = fetch_congress_trades(list(TICKERS.keys()))

    for ticker, name in TICKERS.items():
        t = yf.Ticker(ticker)
        hist = t.history(period="4mo")

        if hist.empty:
            data[ticker] = {
                "name": name, "price": None, "change_pct": None, "news": [],
                "signal": {"score": 50, "signal": "HOLD", "confidence": 0, "reasoning": "No data."},
                "analyst_consensus": None,
                "congress": None,
            }
            continue

        closes = hist["Close"].tolist()
        volumes = hist["Volume"].tolist()
        last_close = float(closes[-1])
        prev_close = float(closes[-2]) if len(closes) > 1 else last_close
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

        stocktwits = fetch_stocktwits_sentiment(ticker)
        analyst_consensus = fetch_analyst_consensus(ticker)
        congress = congress_trades.get(ticker)
        signal = compute_signal(
            closes, volumes, reddit_mentions.get(ticker, 0), stocktwits,
            analyst_consensus=analyst_consensus, congress=congress,
        )

        data[ticker] = {
            "name": name,
            "price": round(last_close, 2),
            "change_pct": round(change_pct, 2),
            "news": news_items,
            "signal": signal,
            "analyst_consensus": analyst_consensus,
            "congress": congress,
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
            macro["treasury_10y"] = round(float(tnx_hist["Close"].iloc[-1]), 2)
    except Exception:
        pass

    return macro


def fetch_fear_greed():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        **BROWSER_HEADERS,
        "Referer": "https://www.cnn.com/markets/fear-and-greed",
        "Origin": "https://www.cnn.com",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
        fg = payload.get("fear_and_greed", {})
        score = fg.get("score")
        rating = fg.get("rating")
        if score is not None:
            return {"score": round(float(score)), "rating": rating, "estimated": False}
    except Exception:
        pass

    return _estimate_fear_greed()


def _estimate_fear_greed():
    try:
        vix_hist = yf.Ticker("^VIX").history(period="1y")
        if vix_hist.empty:
            return {"score": None, "rating": None, "estimated": True}
        current_vix = float(vix_hist["Close"].iloc[-1])
        vix_low = float(vix_hist["Close"].min())
        vix_high = float(vix_hist["Close"].max())
        if vix_high == vix_low:
            return {"score": None, "rating": None, "estimated": True}
        normalized = (current_vix - vix_low) / (vix_high - vix_low)
        score = round((1 - normalized) * 100)
        if score >= 75:
            rating = "Extreme Greed"
        elif score >= 55:
            rating = "Greed"
        elif score >= 45:
            rating = "Neutral"
        elif score >= 25:
            rating = "Fear"
        else:
            rating = "Extreme Fear"
        return {"score": score, "rating": rating, "estimated": True}
    except Exception:
        return {"score": None, "rating": None, "estimated": True}


def fetch_all():
    return {
        "stocks": fetch_stock_data(),
        "macro": fetch_macro_data(),
        "fear_greed": fetch_fear_greed(),
        "reddit": fetch_reddit_top_posts(),
    }
