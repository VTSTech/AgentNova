#!/usr/bin/env python3
"""
crypto_signal_agent.py — Zero-dependency crypto signal fetcher.

Usage (from AgentNova shell tool):
  python crypto_signal_agent.py fetch-prices
  python crypto_signal_agent.py fetch-history bitcoin 30
  python crypto_signal_agent.py fetch-history ethereum 30
  python crypto_signal_agent.py analyze bitcoin ethereum
  python crypto_signal_agent.py full-report

All output is JSON to stdout for easy parse_json consumption.
No pip dependencies — stdlib only.
"""

import json
import math
import sys
import time
import urllib.request
import urllib.error
import os

USER_AGENT = "AgentNova-CryptoSignals/1.0"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINCAP_BASE = "https://api.coincap.io/v2"
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

LOG_FILE = os.path.join(os.getcwd(), "crypto_signals_log.json")

# ─── HTTP helper ────────────────────────────────────────────────────────────

def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": True, "_status": e.code, "_url": url}
    except Exception as e:
        return {"_error": True, "_status": 0, "_message": str(e), "_url": url}

# ─── Data fetching ──────────────────────────────────────────────────────────

def fetch_crypto_prices():
    """Fetch current BTC and ETH prices from CoinGecko."""
    url = (
        f"{COINGECKO_BASE}/simple/price"
        f"?ids=bitcoin,ethereum"
        f"&vs_currencies=usd"
        f"&include_24hr_change=true"
        f"&include_24hr_vol=true"
        f"&include_market_cap=true"
    )
    data = fetch_json(url)
    if data.get("_error"):
        # Fallback to CoinCap
        url2 = f"{COINCAP_BASE}/assets?ids=bitcoin,ethereum"
        data2 = fetch_json(url2)
        if not data2.get("_error"):
            result = {}
            for asset in data2.get("data", []):
                symbol = asset.get("symbol", "").upper()
                result[symbol] = {
                    "usd": float(asset.get("priceUsd", 0)),
                    "usd_24h_change": float(asset.get("changePercent24Hr", 0)),
                    "usd_24h_vol": float(asset.get("volumeUsd24Hr", 0)),
                    "usd_market_cap": float(asset.get("marketCapUsd", 0)),
                    "_source": "coincap"
                }
            return result
        return data
    result = {}
    for key, val in data.items():
        symbol = "BTC" if key == "bitcoin" else "ETH"
        result[symbol] = {**val, "_source": "coingecko"}
    return result

def fetch_crypto_history(coin_id, days=30):
    """Fetch historical price data. coin_id = 'bitcoin' or 'ethereum'."""
    url = (
        f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={days}&interval=daily"
    )
    data = fetch_json(url)
    if data.get("_error"):
        return data
    # Extract just prices
    prices = [p[1] for p in data.get("prices", [])]
    volumes = [v[1] for v in data.get("total_volumes", [])]
    return {"prices": prices, "volumes": volumes, "count": len(prices)}

def fetch_stock_price(ticker):
    """Fetch stock price from Yahoo Finance."""
    url = f"{YAHOO_BASE}/{ticker}?range=1d&interval=1h"
    data = fetch_json(url)
    if data.get("_error"):
        return data
    try:
        result = data["chart"]["result"][0]
        meta = result["meta"]
        quotes = result["indicators"]["quote"][0]
        closes = [c for c in quotes.get("close", []) if c is not None]
        prev_close = closes[-2] if len(closes) >= 2 else closes[-1] if closes else 0
        current = meta.get("regularMarketPrice", closes[-1] if closes else 0)
        change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0
        return {
            "symbol": ticker,
            "price": current,
            "change_pct": round(change_pct, 2),
            "market_cap": meta.get("marketCap"),
            "_source": "yahoo"
        }
    except (KeyError, IndexError, TypeError) as e:
        return {"_error": True, "_message": f"Parse error: {e}"}

# ─── Technical indicators ───────────────────────────────────────────────────

def compute_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        return 100.0
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)

def compute_sma(prices, period=20):
    if len(prices) < period:
        return None
    return round(sum(prices[-period:]) / period, 2)

def compute_ema(prices, period=12):
    if len(prices) < period:
        return None
    mult = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = (p - ema) * mult + ema
    return round(ema, 2)

def compute_macd(prices, fast=12, slow=26, signal_period=9):
    if len(prices) < slow + signal_period:
        return None, None, None
    ema_fast = compute_ema(prices, fast)
    ema_slow = compute_ema(prices, slow)
    if ema_fast is None or ema_slow is None:
        return None, None, None
    macd_line = round(ema_fast - ema_slow, 4)
    macd_vals = []
    for i in range(slow, len(prices) + 1):
        ef = compute_ema(prices[:i], fast)
        es = compute_ema(prices[:i], slow)
        if ef is not None and es is not None:
            macd_vals.append(ef - es)
    signal = compute_ema(macd_vals, signal_period) if len(macd_vals) >= signal_period else macd_line
    histogram = round(macd_line - (signal or 0), 4)
    return macd_line, round(signal, 4) if signal else 0, histogram

def compute_bollinger(prices, period=20, std_dev=2):
    if len(prices) < period:
        return None, None, None
    sma = compute_sma(prices, period)
    recent = prices[-period:]
    variance = sum((p - sma) ** 2 for p in recent) / period
    std = math.sqrt(variance)
    upper = round(sma + std_dev * std, 2)
    lower = round(sma - std_dev * std, 2)
    return upper, round(sma, 2), lower

def full_analysis(prices):
    rsi = compute_rsi(prices, 14)
    sma = compute_sma(prices, 20)
    ema12 = compute_ema(prices, 12)
    ema26 = compute_ema(prices, 26)
    macd, signal, hist = compute_macd(prices)
    bb_upper, bb_mid, bb_lower = compute_bollinger(prices)
    bb_pos = None
    if bb_upper and bb_lower and bb_upper != bb_lower:
        bb_pos = round((prices[-1] - bb_lower) / (bb_upper - bb_lower), 3)
    return {
        "current_price": prices[-1] if prices else None,
        "data_points": len(prices),
        "rsi_14": rsi,
        "sma_20": sma,
        "ema_12": ema12,
        "ema_26": ema26,
        "macd": macd,
        "macd_signal": signal,
        "macd_histogram": hist,
        "bb_upper": bb_upper,
        "bb_middle": bb_mid,
        "bb_lower": bb_lower,
        "bb_position": bb_pos  # 0.0=at lower band, 1.0=at upper band
    }

def generate_signal(analysis):
    """Generate a trading signal based on computed indicators."""
    if not analysis or analysis.get("rsi_14") is None:
        return {"signal": "HOLD", "confidence": "LOW", "reason": "Insufficient data"}
    
    rsi = analysis["rsi_14"]
    bb_pos = analysis.get("bb_position")
    macd_hist = analysis.get("macd_histogram", 0)
    price = analysis["current_price"]
    sma = analysis.get("sma_20")
    
    buy_score = 0
    sell_score = 0
    
    # RSI signals
    if rsi < 25:
        buy_score += 3
    elif rsi < 30:
        buy_score += 2
    elif rsi < 35:
        buy_score += 1
    elif rsi > 75:
        sell_score += 3
    elif rsi > 70:
        sell_score += 2
    elif rsi > 65:
        sell_score += 1
    
    # Bollinger position
    if bb_pos is not None:
        if bb_pos < 0.1:
            buy_score += 2
        elif bb_pos < 0.2:
            buy_score += 1
        elif bb_pos > 0.9:
            sell_score += 2
        elif bb_pos > 0.8:
            sell_score += 1
    
    # MACD histogram
    if macd_hist > 0 and macd_hist > analysis.get("macd_signal", 0):
        buy_score += 1
    elif macd_hist < 0 and macd_hist < analysis.get("macd_signal", 0):
        sell_score += 1
    
    # Price vs SMA
    if sma and price:
        if price < sma * 0.98:
            buy_score += 1
        elif price > sma * 1.02:
            sell_score += 1
    
    # Determine signal
    if buy_score >= 4:
        return {"signal": "STRONG BUY", "confidence": "HIGH", "buy_score": buy_score, "sell_score": sell_score}
    elif buy_score >= 2:
        return {"signal": "BUY", "confidence": "MEDIUM", "buy_score": buy_score, "sell_score": sell_score}
    elif sell_score >= 4:
        return {"signal": "STRONG SELL", "confidence": "HIGH", "buy_score": buy_score, "sell_score": sell_score}
    elif sell_score >= 2:
        return {"signal": "SELL", "confidence": "MEDIUM", "buy_score": buy_score, "sell_score": sell_score}
    else:
        return {"signal": "HOLD", "confidence": "MEDIUM", "buy_score": buy_score, "sell_score": sell_score}

# ─── Logging ────────────────────────────────────────────────────────────────

def log_signals(signals, portfolio_value):
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "signals": signals,
        "portfolio_value": portfolio_value,
    }
    existing = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []
    existing.append(entry)
    # Keep last 100 entries
    existing = existing[-100:]
    with open(LOG_FILE, "w") as f:
        json.dump(existing, f, indent=2)
    return LOG_FILE

# ─── CLI Commands ───────────────────────────────────────────────────────────

def cmd_fetch_prices():
    crypto = fetch_crypto_prices()
    stocks = {}
    for ticker in ["COIN", "MSTR"]:
        s = fetch_stock_price(ticker)
        if not s.get("_error"):
            stocks[ticker] = s
    print(json.dumps({"crypto": crypto, "stocks": stocks}, indent=2))

def cmd_fetch_history(coin_id, days=30):
    data = fetch_crypto_history(coin_id, days)
    print(json.dumps(data, indent=2))

def cmd_analyze(*coins):
    results = {}
    for coin_id in coins:
        hist = fetch_crypto_history(coin_id, 30)
        if hist.get("_error") or not hist.get("prices"):
            results[coin_id] = {"error": "Failed to fetch history", "raw": hist}
            continue
        analysis = full_analysis(hist["prices"])
        signal = generate_signal(analysis)
        results[coin_id] = {"analysis": analysis, "signal": signal}
    print(json.dumps(results, indent=2))

def cmd_full_report():
    # 1. Fetch prices
    prices = fetch_crypto_prices()
    stocks = {}
    for ticker in ["COIN", "MSTR"]:
        s = fetch_stock_price(ticker)
        if not s.get("_error"):
            stocks[ticker] = s
    
    # 2. Analyze BTC and ETH
    analysis_results = {}
    for coin_id in ["bitcoin", "ethereum"]:
        hist = fetch_crypto_history(coin_id, 30)
        if hist.get("prices"):
            a = full_analysis(hist["prices"])
            s = generate_signal(a)
            analysis_results[coin_id] = {"analysis": a, "signal": s}
    
    # 3. Generate report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prices": prices,
        "stocks": stocks,
        "analysis": analysis_results,
        "portfolio": {
            "BTC": {"value": 5.00, "signal": analysis_results.get("bitcoin", {}).get("signal", {}).get("signal", "N/A")},
            "ETH": {"value": 5.00, "signal": analysis_results.get("ethereum", {}).get("signal", {}).get("signal", "N/A")},
            "total": 10.00
        }
    }
    
    # 4. Log
    signals_log = {}
    for coin_id in ["bitcoin", "ethereum"]:
        sym = "BTC" if coin_id == "bitcoin" else "ETH"
        signals_log[sym] = analysis_results.get(coin_id, {}).get("signal", {})
    log_signals(signals_log, 10.00)
    
    print(json.dumps(report, indent=2))

# ─── Main ───────────────────────────────────────────────────────────────────

COMMANDS = {
    "fetch-prices": cmd_fetch_prices,
    "full-report": cmd_full_report,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python crypto_signal_agent.py <command> [args]",
            "commands": list(COMMANDS.keys()) + ["fetch-history <coin_id> [days]", "analyze <coin_id1> [coin_id2] ..."]
        }))
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "fetch-history":
        coin_id = sys.argv[2] if len(sys.argv) > 2 else "bitcoin"
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        cmd_fetch_history(coin_id, days)
    elif cmd == "analyze":
        coins = sys.argv[2:] if len(sys.argv) > 2 else ["bitcoin", "ethereum"]
        cmd_analyze(*coins)
    elif cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}", "available": list(COMMANDS.keys())}))
        sys.exit(1)
