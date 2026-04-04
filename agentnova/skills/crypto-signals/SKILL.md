---
name: crypto-signals
description: "Generate trading signals for cryptocurrency (BTC, ETH) and crypto-adjacent stocks (COIN, MSTR) using free market data APIs, technical analysis, and LLM interpretation. Use when asked to analyze crypto prices, generate buy/sell/hold signals, check portfolio status, or run the crypto signal workflow. Triggers on phrases like 'crypto signals', 'check my portfolio', 'analyze BTC', 'trading signals', 'market analysis', 'should I buy or sell'."
license: MIT
allowed-tools: http_get python_repl calculator shell write_file read_file get_time get_date parse_json
---

# Crypto Trading Signals

Passive income signal generation for a $10 crypto portfolio: $5 BTC, $5 ETH, plus crypto-adjacent stocks COIN (Coinbase) and MSTR (MicroStrategy).

## Portfolio

```
ASSET  | TYPE    | VALUE
-------|---------|--------
BTC    | Crypto  | $5.00
ETH    | Crypto  | $5.00
COIN   | Stock   | Track only
MSTR   | Stock   | Track only
```

COIN and MSTR are stocks, not cryptocurrencies. They correlate with BTC but trade on stock exchanges with different hours and mechanics.

## Workflow

When triggered, follow this sequence:

### Step 1: Fetch Current Prices

Use `http_get` to fetch current market data. Use these free APIs (no API key needed):

**Crypto (BTC, ETH):**
- Primary: `https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true`
- Fallback: `https://api.coincap.io/v2/assets?ids=bitcoin,ethereum`

**Stocks (COIN, MSTR):**
- Primary: `https://query1.finance.yahoo.com/v8/finance/chart/COIN?range=1d&interval=1h`
- Fallback: `https://query1.finance.yahoo.com/v8/finance/chart/MSTR?range=1d&interval=1h`

If CoinGecko rate-limits (429), fall back to CoinCap. If Yahoo fails, note it and proceed with crypto-only analysis.

Parse JSON response with `parse_json` or `python_repl`.

### Step 2: Fetch Historical Data for Technical Analysis

Use `http_get` to pull historical price data for BTC and ETH:

```
https://api.coingecko.com/api/v3/coins/{id}/market_chart?vs_currency=usd&days=30&interval=daily
```

This returns `{prices: [[timestamp, price], ...], market_caps: [...], total_volumes: [...]}`.

Extract the `prices` array. You need at least 14 data points for RSI, 20 for Bollinger Bands, and 26+ for MACD.

### Step 3: Compute Technical Indicators

Use `python_repl` to compute these indicators from the historical price data. See `references/indicators.md` for the formulas.

**Required indicators per asset:**

1. **RSI (14-period)** — Momentum oscillator, 0-100 scale. Overbought >70, Oversold <30.
2. **SMA (20-period)** — Simple Moving Average, trend direction.
3. **EMA (12-period)** — Exponential Moving Average, faster trend signal.
4. **MACD (12,26,9)** — Convergence/divergence of two EMAs. Signal line crossover = trend change.
5. **Bollinger Bands (20,2)** — Volatility envelope. Price near upper band = overbought, lower = oversold.
6. **24h Price Change %** — From current price API response.
7. **24h Volume** — From current price API response.

Use the `calculator` tool or `python_repl` for computations. For complex multi-step calculations, `python_repl` is preferred.

### Step 4: Generate Signal

After computing indicators, use your reasoning to generate a signal for each asset:

```
SIGNAL ANALYSIS: {asset}
================================
Price: ${price}
24h Change: {change}%
24h Volume: ${volume}
RSI(14): {rsi} [{zone}]
SMA(20): ${sma}
EMA(12): ${ema}
MACD: {macd} / Signal: {signal} / Histogram: {hist}
Bollinger: Upper=${upper} Middle=${middle} Lower=${lower}
Price Position: {where price sits within bands}

SIGNAL: {BUY / HOLD / SELL}
CONFIDENCE: {HIGH / MEDIUM / LOW}
RATIONALE: {1-2 sentence reasoning based on indicator consensus}
```

**Signal Logic Guidelines:**

| Condition | Signal |
|-----------|--------|
| RSI < 30 + Price below lower BB + MACD crossover | STRONG BUY |
| RSI < 35 + 2 of: Price < SMA, MACD rising, Volume spike | BUY |
| Indicators mixed / no clear trend | HOLD |
| RSI > 70 + Price above upper BB + MACD crossover down | STRONG SELL |
| RSI > 65 + 2 of: Price > SMA, MACD falling, Volume declining | SELL |

For HOLD signals on an asset already in portfolio, add:
- "Rebalance consideration: {suggest moving funds between BTC/ETH if one significantly outperforms}"

### Step 5: Portfolio Summary

After analyzing all assets, produce a portfolio summary:

```
PORTFOLIO STATUS
================
Date: {current date/time}

Holdings:
  BTC: ${btc_value} ({btc_change_24h}% 24h) — Signal: {signal}
  ETH: ${eth_value} ({eth_change_24h}% 24h) — Signal: {signal}

Tracking (not held):
  COIN: ${coin_price} ({coin_change}% 24h) — Signal: {signal}
  MSTR: ${mstr_price} ({mstr_change}% 24h) — Signal: {signal}

Total Portfolio Value: ${total}
24h P&L: ${pnl} ({pnl_pct}%)

RECOMMENDED ACTION: {one-sentence portfolio-level recommendation}
```

### Step 6: Log Results

Use `write_file` to append results to `crypto_signals_log.json` in the working directory.

Format each entry as:
```json
{
  "timestamp": "2026-04-04T12:00:00",
  "signals": {
    "BTC": {"signal": "HOLD", "confidence": "MEDIUM", "price": 85000, "rsi": 55},
    "ETH": {"signal": "BUY", "confidence": "LOW", "price": 1800, "rsi": 28}
  },
  "portfolio_value": 10.00,
  "pnl_24h_pct": 2.3
}
```

If the file exists, read it first with `read_file`, parse, append the new entry, and write back.

## Constraints

- **Zero dependencies**: All scripts use Python stdlib only (urllib, json, math, datetime)
- **Free APIs only**: CoinGecko (no key, 10-50 req/min), CoinCap (no key), Yahoo Finance (no key)
- **No financial advice**: Signals are for educational/research purposes only
- **Rate limiting**: If CoinGecko returns 429, wait and retry or use CoinCap fallback
- **COIN/MSTR distinction**: These are stocks, not crypto. Flag this in output. They trade Mon-Fri 9:30AM-4PM ET. Crypto trades 24/7.

## Quick Commands

When the user says:
- "Run signals" or "Analyze market" → Execute full workflow Steps 1-6
- "Check prices" → Execute Step 1 only, show current prices
- "How's my portfolio" → Execute Steps 1 + 5, skip technical analysis
- "Detailed analysis on BTC" → Execute full workflow for BTC only

## Asset IDs Reference

| Asset | CoinGecko ID | Yahoo Ticker |
|-------|-------------|--------------|
| BTC | bitcoin | BTC-USD |
| ETH | ethereum | ETH-USD |
| COIN | — | COIN |
| MSTR | — | MSTR |
