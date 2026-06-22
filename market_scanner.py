import os
from datetime import datetime
import anthropic

TICKERS = {
    "VOO":  "Vanguard S&P 500 ETF",
    "QQQM": "Invesco Nasdaq 100 ETF",
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "SPY":  "SPDR S&P 500 ETF",
}

def get_market_sentiment() -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now().strftime("%B %d, %Y")
    ticker_list = ", ".join(TICKERS.keys())

    prompt = f"""You are a financial market analyst. Today is {today}.

For each of these tickers: {ticker_list}

Search for the latest news, Reddit/WSB sentiment, earnings updates, Fed/macro signals, and analyst calls.

Respond in this EXACT format, one line per ticker:

TICKER_SYMBOL|SCORE|SIGNAL|SUMMARY

- SCORE: 0-100 (0=very bearish, 50=neutral, 100=very bullish)
- SIGNAL: exactly BUY, HOLD, or REDUCE
- SUMMARY: 1-2 sentences, max 200 chars

Output one line per ticker, nothing else."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = "\n".join(b.text for b in response.content if b.type == "text")

    results = {}
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        ticker, score_str, signal, summary = parts
        ticker = ticker.strip().upper()
        if ticker not in TICKERS:
            continue
        try:
            score = max(0, min(100, int(score_str.strip())))
        except ValueError:
            score = 50
        signal = signal.strip().upper()
        if signal not in ("BUY", "HOLD", "REDUCE"):
            signal = "HOLD"
        results[ticker] = {
            "name":    TICKERS[ticker],
            "score":   score,
            "signal":  signal,
            "summary": summary.strip(),
        }

    for t in TICKERS:
        if t not in results:
            results[t] = {"name": TICKERS[t], "score": 50, "signal": "HOLD", "summary": "No data retrieved."}

    return results


def build_sms(results: dict) -> str:
    today = datetime.now().strftime("%a %b %d")
    signal_emoji = {"BUY": "✅", "HOLD": "🟡", "REDUCE": "🔴"}
    lines = [f"MARKET SCAN - {today}", ""]

    for ticker, data in results.items():
        emoji = signal_emoji.get(data["signal"], "⬜")
        lines.append(f"{emoji} {ticker} ({data['score']}/100) - {data['signal']}")
        lines.append(f"   {data['summary'][:120]}")
        lines.append("")

    avg = round(sum(d["score"] for d in results.values()) / len(results))
    buys   = sum(1 for d in results.values() if d["signal"] == "BUY")
    holds  = sum(1 for d in results.values() if d["signal"] == "HOLD")
    reduce = sum(1 for d in results.values() if d["signal"] == "REDUCE")

    lines.append(f"Portfolio avg: {avg}/100")
    lines.append(f"Buy:{buys} Hold:{holds} Reduce:{reduce}")

    return "\n".join(lines)
