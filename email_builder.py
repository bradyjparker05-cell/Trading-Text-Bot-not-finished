from datetime import datetime

NAVY = "#0b1e33"
CARD = "#f4f6f9"
GREEN = "#1e8a4c"
RED = "#c0392b"
GRAY = "#5a6673"


def _change_color(change_pct):
    if change_pct is None:
        return GRAY
    return GREEN if change_pct >= 0 else RED


def _signal_color(signal):
    return {"BUY": GREEN, "REDUCE": RED, "HOLD": "#b8860b"}.get(signal, GRAY)


def _pill(text, color):
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:12px;'
        f'background:{color};color:#ffffff;font-size:12px;font-weight:600;">{text}</span>'
    )


def _gauge_bar(score):
    if score is None:
        return "<p style='color:#888;font-size:13px;'>Fear &amp; Greed data unavailable.</p>"

    pos_pct = max(0, min(100, score))
    return f"""
    <div style="margin:10px 0 4px 0;">
        <div style="background:linear-gradient(to right, #c0392b, #e1b12c, #1e8a4c);
                    height:10px;border-radius:5px;position:relative;">
            <div style="position:absolute;left:{pos_pct}%;top:-5px;transform:translateX(-50%);
                        width:2px;height:20px;background:#0b1e33;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin-top:2px;">
            <span>Extreme Fear</span><span>Neutral</span><span>Extreme Greed</span>
        </div>
    </div>
    """


def _analyst_consensus_html(consensus):
    if not consensus:
        return ""
    total = (consensus["strong_buy"] + consensus["buy"] + consensus["hold"]
             + consensus["sell"] + consensus["strong_sell"])
    if total == 0:
        return ""
    buy_total = consensus["strong_buy"] + consensus["buy"]
    return (
        f'<div style="font-size:11px;color:{GRAY};margin-top:4px;">'
        f'Wall Street ({consensus.get("period","")}): '
        f'<strong style="color:{NAVY};">{buy_total} Buy</strong> · '
        f'{consensus["hold"]} Hold · '
        f'{consensus["sell"] + consensus["strong_sell"]} Sell '
        f'({total} analysts)</div>'
    )


def _congress_html(congress):
    if not congress:
        return ""
    buys, sells = congress.get("buys", 0), congress.get("sells", 0)
    if buys + sells == 0:
        return ""
    return (
        f'<div style="font-size:11px;color:{GRAY};margin-top:2px;">'
        f'Congress (45d): <strong style="color:{NAVY};">{buys} buys</strong> · {sells} sells</div>'
    )


def _stock_row(ticker, info):
    price = f"${info['price']:,.2f}" if info["price"] is not None else "N/A"
    change = info["change_pct"]
    change_str = f"{change:+.2f}%" if change is not None else "N/A"
    pill = _pill(change_str, _change_color(change))

    signal = info.get("signal", {})
    sig_label = signal.get("signal", "HOLD")
    sig_score = signal.get("score", 50)
    sig_conf = signal.get("confidence", 0)
    sig_reason = signal.get("reasoning", "")
    sig_pill = _pill(f"{sig_label} · {sig_score}/100", _signal_color(sig_label))

    news_html = ""
    for item in info.get("news", [])[:2]:
        news_html += f'<div style="font-size:12px;margin-top:4px;"><a href="{item["link"]}" style="color:{NAVY};text-decoration:none;">&#8226; {item["title"]}</a></div>'

    consensus_html = _analyst_consensus_html(info.get("analyst_consensus"))
    congress_html = _congress_html(info.get("congress"))

    return f"""
    <tr style="border-bottom:1px solid #e2e6ea;">
        <td style="padding:12px 8px;">
            <strong>{ticker}</strong><br>
            <span style="font-size:12px;color:{GRAY};">{info['name']}</span>
        </td>
        <td style="padding:12px 8px;text-align:right;">{price}</td>
        <td style="padding:12px 8px;text-align:right;">{pill}</td>
    </tr>
    <tr style="border-bottom:1px solid #e2e6ea;">
        <td colspan="3" style="padding:0 8px 4px 8px;">
            {sig_pill} <span style="font-size:11px;color:{GRAY};">signal confidence {sig_conf}%</span>
            <div style="font-size:12px;color:{GRAY};margin-top:4px;">{sig_reason}</div>
            {consensus_html}
            {congress_html}
            {news_html}
        </td>
    </tr>
    """


def _reddit_section(posts):
    if not posts:
        return ""
    items = ""
    for post in posts[:5]:
        items += f'<div style="font-size:13px;margin-bottom:6px;"><a href="{post["link"]}" style="color:{NAVY};text-decoration:none;">&#8226; {post["title"]}</a> <span style="color:{GRAY};font-size:11px;">({post["score"]} upvotes)</span></div>'
    return f"""
    <div style="background:{CARD};border-radius:8px;padding:16px;margin-top:20px;">
        <h3 style="margin:0 0 10px 0;font-size:15px;color:{NAVY};">r/wallstreetbets — Hot Right Now</h3>
        {items}
    </div>
    """


def build_email(data):
    today = datetime.now().strftime("%A, %B %d, %Y")
    stocks = data["stocks"]
    macro = data["macro"]
    fear_greed = data["fear_greed"]
    reddit = data["reddit"]

    vix = macro.get("vix")
    tnx = macro.get("treasury_10y")
    vix_str = f"{vix:.2f}" if vix is not None else "N/A"
    tnx_str = f"{tnx:.2f}%" if tnx is not None else "N/A"

    fg_score = fear_greed.get("score")
    fg_rating = fear_greed.get("rating") or "Unavailable"
    fg_score_str = f"{fg_score}/100" if fg_score is not None else "N/A"
    fg_note = " (estimated from VIX)" if fear_greed.get("estimated") and fg_score is not None else ""

    rows_html = "".join(_stock_row(ticker, info) for ticker, info in stocks.items())
    reddit_html = _reddit_section(reddit)

    valid_changes = [i["change_pct"] for i in stocks.values() if i["change_pct"] is not None]
    avg_change = round(sum(valid_changes) / len(valid_changes), 2) if valid_changes else None
    avg_str = f"{avg_change:+.2f}%" if avg_change is not None else "N/A"

    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#eef1f4;font-family:Arial, Helvetica, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#eef1f4;padding:24px 0;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;overflow:hidden;">
                        <tr>
                            <td style="background:{NAVY};padding:24px 28px;">
                                <h1 style="color:#ffffff;margin:0;font-size:20px;">Market Report</h1>
                                <p style="color:#b8c4d1;margin:4px 0 0 0;font-size:13px;">{today}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:24px 28px;">
                                <h3 style="margin:0 0 4px 0;font-size:14px;color:{NAVY};">Fear &amp; Greed Index — {fg_rating} ({fg_score_str}){fg_note}</h3>
                                {_gauge_bar(fg_score)}
                                <div style="display:flex;gap:16px;margin-top:16px;font-size:13px;color:{GRAY};">
                                    <div>VIX: <strong style="color:{NAVY};">{vix_str}</strong></div>
                                    <div>10Y Treasury: <strong style="color:{NAVY};">{tnx_str}</strong></div>
                                    <div>Portfolio avg: <strong style="color:{NAVY};">{avg_str}</strong></div>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:0 28px 8px 28px;">
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    {rows_html}
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:0 28px 28px 28px;">
                                {reddit_html}
                            </td>
                        </tr>
                        <tr>
                            <td style="background:{CARD};padding:14px 28px;text-align:center;">
                                <p style="margin:0;font-size:11px;color:{GRAY};">Signals are computed algorithmically from RSI, moving averages, momentum, volume, and public sentiment data — not real analyst opinions. Automated report. Not financial advice.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    subject = f"Market Report — {datetime.now().strftime('%a %b %d')} ({fg_rating})"
    return subject, html
