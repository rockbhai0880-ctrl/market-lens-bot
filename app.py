"""
MARKET LENS SIGNAL BOT
Real-time trading signals using refined multi-timeframe analysis
Real Binance data • Statistical analysis • SMC patterns • Game theory
Deploy on Render.com as a Web Service
"""

from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import requests
import math
import os
import time
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

# ==========================================
# GLOBAL STATE
# ==========================================
STATE = {
    "running": False,
    "paused": False,
    "symbol": "BTCUSDT",
    "risk_percent": 1,
    "balance": 1000,
    "cycles": 0,
    "last_price": 0,
    "last_signal": None,
    "last_analysis": None,
    "logs": []
}

def add_log(msg):
    """Add timestamped log message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    STATE["logs"].append(f"[{timestamp}] {msg}")
    if len(STATE["logs"]) > 100:
        STATE["logs"] = STATE["logs"][-100:]
    print(f"[{timestamp}] {msg}")

# ==========================================
# BINANCE DATA (REAL MARKET DATA)
# ==========================================
BINANCE_URL = "https://api.binance.com/api/v3"

def fetch_klines(symbol, interval, limit=100):
    """Fetch real candlestick data from Binance"""
    try:
        url = f"{BINANCE_URL}/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        candles = []
        for k in data:
            candles.append({
                "time": k[0] // 1000,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })
        return candles
    except Exception as e:
        add_log(f"❌ Binance error ({interval}): {e}")
        return []

def fetch_ticker(symbol):
    """Fetch 24hr ticker and current price"""
    try:
        url = f"{BINANCE_URL}/ticker/24hr"
        response = requests.get(url, params={"symbol": symbol}, timeout=5)
        data = response.json()
        return {
            "price": float(data["lastPrice"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "change": float(data["priceChangePercent"]),
            "volume": float(data["volume"])
        }
    except Exception as e:
        add_log(f"❌ Ticker error: {e}")
        return None

# ==========================================
# STATISTICAL ENGINE (YOUR REFINED FRAMEWORK)
# ==========================================

def calc_sma(data, period):
    """Simple Moving Average"""
    if len(data) < period:
        return None
    closes = [c["close"] for c in data]
    return sum(closes[-period:]) / period

def calc_std(data, period, sma):
    """Standard Deviation"""
    if len(data) < period or sma is None:
        return None
    closes = [c["close"] for c in data[-period:]]
    variance = sum((c - sma) ** 2 for c in closes) / period
    return math.sqrt(variance)

def calc_slope(data):
    """Linear regression slope (% change)"""
    if len(data) < 10:
        return 0
    closes = [c["close"] for c in data]
    first_half = sum(closes[:5]) / 5
    last_half = sum(closes[-5:]) / 5
    if first_half == 0:
        return 0
    return ((last_half - first_half) / first_half) * 100

def calc_rsi(data, period=14):
    """Relative Strength Index"""
    if len(data) < period + 1:
        return None
    closes = [c["close"] for c in data]
    gains = 0
    losses = 0
    for i in range(len(closes) - period, len(closes)):
        change = closes[i] - closes[i-1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    if losses == 0:
        return 100
    avg_gain = gains / period
    avg_loss = losses / period
    return 100 - (100 / (1 + avg_gain / avg_loss))

def calc_atr(data, period=14):
    """Average True Range"""
    if len(data) < period + 1:
        return None
    tr_values = []
    for i in range(1, len(data)):
        h = data[i]["high"]
        l = data[i]["low"]
        pc = data[i-1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_values.append(tr)
    return sum(tr_values[-period:]) / period

# ==========================================
# SMC PATTERN DETECTION
# ==========================================

def detect_fvg(data):
    """Detect Fair Value Gap"""
    if len(data) < 3:
        return {"detected": False, "type": None}
    
    prev = data[-2]
    prev_prev = data[-3]
    
    # Bullish FVG: gap up
    if prev["low"] > prev_prev["high"]:
        return {
            "detected": True,
            "type": "BULLISH_FVG",
            "zone_high": prev["low"],
            "zone_low": prev_prev["high"],
            "reason": "Gap up - inefficient auction"
        }
    
    # Bearish FVG: gap down
    if prev["high"] < prev_prev["low"]:
        return {
            "detected": True,
            "type": "BEARISH_FVG",
            "zone_high": prev_prev["low"],
            "zone_low": prev["high"],
            "reason": "Gap down - inefficient auction"
        }
    
    return {"detected": False, "type": None}

def detect_liquidity_sweep(data):
    """Detect Liquidity Sweep (Stop Hunt)"""
    if len(data) < 12:
        return {"detected": False, "type": None}
    
    last = data[-1]
    lookback = data[-11:-1]
    recent_high = max(c["high"] for c in lookback)
    recent_low = min(c["low"] for c in lookback)
    
    # Bullish sweep: dip below support, then reclaim
    if last["low"] < recent_low and last["close"] > recent_low:
        return {
            "detected": True,
            "type": "BULLISH_SWEEP",
            "level": recent_low,
            "reason": f"Stop hunt below {recent_low:.2f}, reclaimed. Smart money accumulating."
        }
    
    # Bearish sweep: spike above resistance, then reject
    if last["high"] > recent_high and last["close"] < recent_high:
        return {
            "detected": True,
            "type": "BEARISH_SWEEP",
            "level": recent_high,
            "reason": f"Liquidity grab above {recent_high:.2f}, rejected. Smart money distributing."
        }
    
    return {"detected": False, "type": None}

# ==========================================
# REGIME DETECTION (MULTI-FACTOR VOTING)
# ==========================================

def detect_regime(data):
    """
    Detect market regime using multi-factor voting system.
    This is YOUR refined framework.
    """
    if len(data) < 20:
        return {"bias": "NEUTRAL", "regime": "UNKNOWN", "confidence": 0, "reason": "Insufficient data"}
    
    price = data[-1]["close"]
    sma = calc_sma(data, 20)
    std = calc_std(data, 20, sma)
    slope = calc_slope(data)
    rsi = calc_rsi(data)
    atr = calc_atr(data)
    
    if sma is None:
        return {"bias": "NEUTRAL", "regime": "UNKNOWN", "confidence": 0, "reason": "Cannot calculate SMA"}
    
    deviation = ((price - sma) / sma) * 100
    upper_band = sma + (2 * std) if std else sma * 1.05
    lower_band = sma - (2 * std) if std else sma * 0.95
    
    # ==========================================
    # VOTING SYSTEM (Your framework)
    # ==========================================
    bull_votes = 0
    bear_votes = 0
    reasons = []
    
    # 1. Price vs SMA (weight: 2)
    if deviation > 0.5:
        bull_votes += 2
        reasons.append(f"Price {deviation:.2f}% above SMA")
    elif deviation < -0.5:
        bear_votes += 2
        reasons.append(f"Price {abs(deviation):.2f}% below SMA")
    elif deviation > 0.1:
        bull_votes += 1
    elif deviation < -0.1:
        bear_votes += 1
    
    # 2. Slope / Trend direction (weight: 2)
    if slope > 0.1:
        bull_votes += 2
        reasons.append(f"Uptrend slope {slope:.2f}%")
    elif slope < -0.1:
        bear_votes += 2
        reasons.append(f"Downtrend slope {abs(slope):.2f}%")
    elif slope > 0.02:
        bull_votes += 1
    elif slope < -0.02:
        bear_votes += 1
    
    # 3. RSI (weight: 1)
    if rsi is not None:
        if rsi > 55:
            bull_votes += 1
            reasons.append(f"RSI bullish at {rsi:.0f}")
        elif rsi < 45:
            bear_votes += 1
            reasons.append(f"RSI bearish at {rsi:.0f}")
    
    # 4. Bollinger Band position (weight: 1)
    if price > upper_band:
        if slope > 0:
            bull_votes += 1
            reasons.append("Price above upper BB, trending up")
        else:
            bear_votes += 1
            reasons.append("Price above upper BB, potential reversal")
    elif price < lower_band:
        if slope < 0:
            bear_votes += 1
            reasons.append("Price below lower BB, trending down")
        else:
            bull_votes += 1
            reasons.append("Price below lower BB, potential reversal")
    
    # ==========================================
    # DECISION
    # ==========================================
    total = bull_votes + bear_votes
    
    if bull_votes > bear_votes:
        bias = "BULLISH"
        confidence = bull_votes / total if total > 0 else 0.5
        if bull_votes >= 5:
            regime = "STRONG_TREND"
        elif bull_votes >= 3:
            regime = "MILD_TREND"
        else:
            regime = "WEAK_BULLISH"
    elif bear_votes > bull_votes:
        bias = "BEARISH"
        confidence = bear_votes / total if total > 0 else 0.5
        if bear_votes >= 5:
            regime = "STRONG_TREND"
        elif bear_votes >= 3:
            regime = "MILD_TREND"
        else:
            regime = "WEAK_BEARISH"
    else:
        bias = "NEUTRAL"
        confidence = 0.5
        regime = "RANGE"
        reasons.append("Balanced signals, no clear edge")
    
    return {
        "bias": bias,
        "regime": regime,
        "confidence": round(confidence, 3),
        "reason": " | ".join(reasons[:4]) if reasons else "Mixed signals",
        "price": round(price, 2),
        "sma": round(sma, 2),
        "std": round(std, 6) if std else None,
        "upper_band": round(upper_band, 2),
        "lower_band": round(lower_band, 2),
        "deviation_pct": round(deviation, 3),
        "slope_pct": round(slope, 3),
        "rsi": round(rsi, 1) if rsi else None,
        "atr": round(atr, 2) if atr else None,
        "bull_votes": bull_votes,
        "bear_votes": bear_votes
    }

# ==========================================
# SYNTHESIS ENGINE
# ==========================================

def synthesize(strategic, operational, tactical, sweep, fvg):
    """
    Multi-timeframe synthesis with SMC patterns.
    This implements your Nash game theory framework.
    """
    b4 = strategic["bias"]
    b1 = operational["bias"]
    b15 = tactical["bias"]
    
    conf_avg = (strategic["confidence"] + operational["confidence"] + tactical["confidence"]) / 3
    
    # ==========================================
    # CASE 1: PERFECT ALIGNMENT - ALL LONG
    # ==========================================
    if b4 == "BULLISH" and b1 == "BULLISH" and b15 == "BULLISH":
        return {
            "signal": "STRONG_LONG",
            "direction": "LONG",
            "icon": "🟢",
            "confidence": conf_avg,
            "text": "ALL TIMEFRAMES ALIGNED - STRONG BUY",
            "reason": f"4H:{b4} + 1H:{b1} + 15M:{b15}. Perfect bullish alignment.",
            "game_theory": "Smart money has engineered upside. Retail shorts are fuel.",
            "action": "ENTER LONG NOW"
        }
    
    # ==========================================
    # CASE 2: PERFECT ALIGNMENT - ALL SHORT
    # ==========================================
    if b4 == "BEARISH" and b1 == "BEARISH" and b15 == "BEARISH":
        return {
            "signal": "STRONG_SHORT",
            "direction": "SHORT",
            "icon": "🔴",
            "confidence": conf_avg,
            "text": "ALL TIMEFRAMES ALIGNED - STRONG SELL",
            "reason": f"4H:{b4} + 1H:{b1} + 15M:{b15}. Perfect bearish alignment.",
            "game_theory": "Smart money distributing. Retail longs are trapped.",
            "action": "ENTER SHORT NOW"
        }
    
    # ==========================================
    # CASE 3: SMC ACCUMULATION (Bullish Sweep)
    # ==========================================
    if b4 == "BULLISH" and sweep["detected"] and sweep["type"] == "BULLISH_SWEEP":
        return {
            "signal": "SMC_ACCUMULATION",
            "direction": "LONG",
            "icon": "🟢",
            "confidence": 0.75,
            "text": "SMART MONEY ACCUMULATING - STOP HUNT DETECTED",
            "reason": sweep["reason"],
            "game_theory": "Nash equilibrium: Large player needs liquidity. Stop hunt provides counterparty orders.",
            "action": "ENTER LONG AT SWEEP LEVEL",
            "sweep_level": sweep["level"]
        }
    
    # ==========================================
    # CASE 4: SMC DISTRIBUTION (Bearish Sweep)
    # ==========================================
    if b4 == "BEARISH" and sweep["detected"] and sweep["type"] == "BEARISH_SWEEP":
        return {
            "signal": "SMC_DISTRIBUTION",
            "direction": "SHORT",
            "icon": "🔴",
            "confidence": 0.75,
            "text": "SMART MONEY DISTRIBUTING - LIQUIDITY GRAB",
            "reason": sweep["reason"],
            "game_theory": "Large player selling into retail breakout orders. Optimal execution.",
            "action": "ENTER SHORT AT SWEEP LEVEL",
            "sweep_level": sweep["level"]
        }
    
    # ==========================================
    # CASE 5: BULLISH BIAS (Strategic + Operational)
    # ==========================================
    if b4 == "BULLISH" and b1 == "BULLISH":
        return {
            "signal": "BULLISH_BIAS",
            "direction": "LONG",
            "icon": "🟡",
            "confidence": (strategic["confidence"] + operational["confidence"]) / 2,
            "text": "BULLISH STRUCTURE - WAITING FOR TACTICAL TRIGGER",
            "reason": f"4H and 1H bullish. 15M is {b15}. Wait for pullback entry.",
            "game_theory": "Higher timeframe buyers in control. Wait for 15M discount.",
            "action": "PREPARE LONG - WAIT FOR 15M SIGNAL"
        }
    
    # ==========================================
    # CASE 6: BEARISH BIAS (Strategic + Operational)
    # ==========================================
    if b4 == "BEARISH" and b1 == "BEARISH":
        return {
            "signal": "BEARISH_BIAS",
            "direction": "SHORT",
            "icon": "🟡",
            "confidence": (strategic["confidence"] + operational["confidence"]) / 2,
            "text": "BEARISH STRUCTURE - WAITING FOR TACTICAL TRIGGER",
            "reason": f"4H and 1H bearish. 15M is {b15}. Wait for rally entry.",
            "game_theory": "Higher timeframe sellers in control. Wait for 15M premium.",
            "action": "PREPARE SHORT - WAIT FOR 15M SIGNAL"
        }
    
    # ==========================================
    # DEFAULT: NO CLEAR EDGE
    # ==========================================
    return {
        "signal": "NO_EDGE",
        "direction": None,
        "icon": "⚪",
        "confidence": 0,
        "text": "NO HIGH-PROBABILITY SETUP",
        "reason": f"4H:{b4} | 1H:{b1} | 15M:{b15} - Conflicting signals",
        "game_theory": "Multiple agent games in conflict. No Nash equilibrium to exploit.",
        "action": "STAY FLAT - PRESERVE CAPITAL"
    }

# ==========================================
# TRADE LEVEL CALCULATOR
# ==========================================

def calculate_trade_levels(signal, price, balance, risk_percent):
    """Calculate exact entry, SL, TP levels based on signal"""
    if signal["direction"] is None:
        return None
    
    atr = price * 0.008  # Approximate ATR as 0.8% of price
    
    # Entry price
    entry = signal.get("sweep_level", price)
    
    # Stop Loss and Take Profit
    if signal["direction"] == "LONG":
        sl = entry - (atr * 1.5)
        tp = entry + (atr * 3.0)
    else:
        sl = entry + (atr * 1.5)
        tp = entry - (atr * 3.0)
    
    # Position size based on risk
    risk_amount = balance * (risk_percent / 100)
    stop_distance = abs(entry - sl)
    lots = risk_amount / stop_distance if stop_distance > 0 else 0.01
    
    # Risk:Reward ratio
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    
    return {
        "entry": round(entry, 2),
        "stop_loss": round(sl, 2),
        "take_profit": round(tp, 2),
        "lot_size": round(min(lots, 1.0), 2),
        "risk_amount": round(risk_amount, 2),
        "risk_reward": round(rr, 1)
    }

# ==========================================
# MAIN ANALYSIS PIPELINE
# ==========================================

def run_full_analysis():
    """Run the complete analysis pipeline"""
    STATE["cycles"] += 1
    
    # 1. Fetch real market data
    add_log(f"📡 Cycle #{STATE['cycles']} - Fetching Binance data...")
    
    c15 = fetch_klines(STATE["symbol"], "15m", 100)
    c1h = fetch_klines(STATE["symbol"], "1h", 100)
    c4h = fetch_klines(STATE["symbol"], "4h", 100)
    ticker = fetch_ticker(STATE["symbol"])
    
    if not ticker:
        add_log("❌ Failed to fetch market data")
        return None
    
    STATE["last_price"] = ticker["price"]
    add_log(f"💰 BTC/USDT: ${ticker['price']:.2f} ({ticker['change']:+.2f}%)")
    
    # 2. Statistical regime detection
    strategic = detect_regime(c4h)
    operational = detect_regime(c1h)
    tactical = detect_regime(c15)
    
    add_log(f"📊 4H: {strategic['bias']} (conf:{strategic['confidence']:.0%}) | "
            f"1H: {operational['bias']} (conf:{operational['confidence']:.0%}) | "
            f"15M: {tactical['bias']} (conf:{tactical['confidence']:.0%})")
    
    # 3. SMC Pattern detection
    sweep = detect_liquidity_sweep(c1h)
    fvg = detect_fvg(c15)
    
    if sweep["detected"]:
        add_log(f"⚠️ SMC PATTERN: {sweep['type']} at {sweep.get('level', 'N/A')}")
    if fvg["detected"]:
        add_log(f"📍 FVG: {fvg['type']}")
    
    # 4. Synthesis
    signal = synthesize(strategic, operational, tactical, sweep, fvg)
    
    add_log(f"🎯 SIGNAL: {signal['text']}")
    add_log(f"🧠 {signal['game_theory']}")
    add_log(f"📋 ACTION: {signal['action']}")
    
    # 5. Calculate trade levels
    levels = calculate_trade_levels(
        signal,
        ticker["price"],
        STATE["balance"],
        STATE["risk_percent"]
    )
    
    if levels:
        add_log(f"🎯 Entry: ${levels['entry']:.2f} | "
                f"SL: ${levels['stop_loss']:.2f} | "
                f"TP: ${levels['take_profit']:.2f}")
        add_log(f"📐 R:R = 1:{levels['risk_reward']} | "
                f"Risk: ${levels['risk_amount']:.2f}")
    
    # Store results
    STATE["last_analysis"] = {
        "ticker": ticker,
        "strategic": strategic,
        "operational": operational,
        "tactical": tactical,
        "sweep": sweep,
        "fvg": fvg,
        "signal": signal,
        "levels": levels
    }
    
    return STATE["last_analysis"]

# ==========================================
# THE WEBSITE (HTML TEMPLATE)
# ==========================================
HTML = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Market Lens Signals</title>
    <style>
        :root{
            --bg:#0a0e14;--card:#12161e;--border:#1e2430;--text:#e1e6ed;
            --muted:#5c6678;--bull:#16c784;--bear:#ea3943;--warn:#f0b90b;--accent:#3b82f6;
        }
        *{margin:0;padding:0;box-sizing:border-box}
        body{
            background:var(--bg);color:var(--text);
            font-family:-apple-system,BlinkMacSystemFont,sans-serif;
            font-size:13px;padding:8px;max-width:500px;margin:0 auto;
        }
        .card{background:var(--card);border-radius:12px;padding:14px;margin-bottom:8px}
        h2{font-size:1rem;color:var(--accent)}
        .sub{font-size:.6rem;color:var(--muted);margin-bottom:8px}
        .fg{margin-bottom:8px}
        .fg label{display:block;font-size:.6rem;color:var(--muted);margin-bottom:2px;text-transform:uppercase}
        .fg input,.fg select{width:100%;padding:10px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.85rem}
        .btn{width:100%;padding:12px;border:none;border-radius:8px;font-size:.85rem;font-weight:600;cursor:pointer;margin-top:4px}
        .btn-blue{background:var(--accent);color:#fff}
        .btn-red{background:var(--bear);color:#fff}
        .hidden{display:none!important}
        .header-row{display:flex;justify-content:space-between;align-items:center}
        .dot{width:8px;height:8px;border-radius:50%;background:var(--bull);display:inline-block;animation:pulse 1.5s infinite}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
        
        .price-bar{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--card);border-radius:10px;margin-bottom:8px}
        .price-main{font-size:1.2rem;font-weight:700}
        .price-change{font-size:.7rem;padding:3px 8px;border-radius:4px}
        .price-change.up{color:var(--bull);background:rgba(22,199,132,.15)}
        .price-change.down{color:var(--bear);background:rgba(234,57,67,.15)}
        
        .sig-card{text-align:center;padding:16px;border:2px solid var(--border);border-radius:12px;margin-bottom:8px;transition:all .3s}
        .sig-card.long{border-color:var(--bull);background:rgba(22,199,132,.05);box-shadow:0 0 20px rgba(22,199,132,.1)}
        .sig-card.short{border-color:var(--bear);background:rgba(234,57,67,.05);box-shadow:0 0 20px rgba(234,57,67,.1)}
        .sig-icon{font-size:2.5rem}
        .sig-text{font-size:1rem;font-weight:700;margin:4px 0}
        .sig-action{font-size:.75rem;color:var(--accent);font-weight:600;margin-bottom:6px}
        .sig-bar{height:4px;background:var(--border);border-radius:2px;margin:6px 0;overflow:hidden}
        .sig-fill{height:100%;transition:width .5s}
        .sig-conf{font-size:.6rem;color:var(--muted)}
        .sig-reason{font-size:.6rem;color:var(--muted);margin-top:4px;line-height:1.3}
        
        .levels-card{background:#0a111a;border-radius:12px;padding:12px;margin-bottom:8px;border:1px solid var(--accent)}
        .levels-title{font-size:.6rem;color:var(--accent);margin-bottom:8px;letter-spacing:.5px}
        .level-row{display:flex;justify-content:space-between;align-items:center;font-size:.7rem;margin-bottom:4px}
        .level-row span:first-child{color:var(--muted)}
        .level-row span:last-child{font-weight:600}
        .copy-btn{background:var(--border);color:var(--text);border:none;padding:3px 8px;border-radius:3px;font-size:.55rem;cursor:pointer}
        .copy-btn:active{background:var(--accent)}
        
        .tf-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-bottom:8px}
        .tf-box{background:var(--card);border-radius:8px;padding:10px 6px;text-align:center}
        .tf-label{font-size:.5rem;padding:1px 5px;border-radius:3px;background:var(--border);display:inline-block}
        .tf-bias{display:block;font-size:.7rem;font-weight:700;margin:4px 0}
        .tf-bias.bull{color:var(--bull)}.tf-bias.bear{color:var(--bear)}.tf-bias.neut{color:var(--warn)}
        .tf-conf{font-size:.5rem;color:var(--muted)}
        .tf-detail{font-size:.5rem;color:var(--muted);line-height:1.3;margin-top:2px}
        
        .ctrl-row{display:flex;gap:4px;margin-bottom:8px}
        .ctrl-row button{flex:1;padding:8px;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:8px;font-size:.6rem;cursor:pointer}
        
        .log-box{background:#000;border-radius:8px;padding:8px;max-height:100px;overflow-y:auto}
        .log-msg{font-family:monospace;font-size:.5rem;color:#00ff88;line-height:1.3}
        
        .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;padding:8px 16px;border-radius:20px;font-size:.75rem;opacity:0;transition:opacity .3s;z-index:100}
        .toast.show{opacity:1}
    </style>
</head>
<body>

<!-- SETUP SCREEN -->
<div id="setup" class="card">
    <h2>📊 Market Lens Signals</h2>
    <p class="sub">Multi-Timeframe Analysis • SMC Patterns • Game Theory</p>
    <div class="fg"><label>Your Balance ($)</label><input type="number" id="balance" value="1000"></div>
    <div class="fg"><label>Risk Per Trade (%)</label><input type="number" id="risk" value="1" min="0.1" max="5" step="0.1"></div>
    <button class="btn btn-blue" onclick="startBot()">▶ Start Signal Bot</button>
    <div id="setupStatus" style="font-size:.65rem;color:var(--muted);text-align:center;margin-top:8px;"></div>
</div>

<!-- DASHBOARD -->
<div id="dashboard" class="hidden">
    <div class="header-row card">
        <h2>🤖 Market Lens</h2>
        <div style="display:flex;align-items:center;gap:6px;">
            <div class="dot"></div>
            <span style="font-size:.55rem;color:var(--muted);">Cycle <span id="cyc">0</span></span>
        </div>
    </div>
    
    <div class="price-bar">
        <span style="font-size:.6rem;color:var(--muted);">BTC/USDT</span>
        <span class="price-main" id="price">---</span>
        <span class="price-change" id="change">---</span>
    </div>
    
    <div class="sig-card" id="sigCard">
        <div class="sig-icon" id="sigIcon">⚪</div>
        <div class="sig-text" id="sigText">WAITING</div>
        <div class="sig-action" id="sigAction">---</div>
        <div class="sig-bar"><div class="sig-fill" id="sigFill"></div></div>
        <div class="sig-conf" id="sigConf">---</div>
        <div class="sig-reason" id="sigReason"></div>
    </div>
    
    <div class="levels-card hidden" id="levelsCard">
        <div class="levels-title">📋 TRADE LEVELS - COPY TO MT5</div>
        <div class="level-row"><span>🎯 Entry</span><span id="lEntry">---</span><button class="copy-btn" onclick="copyVal('lEntry')">Copy</button></div>
        <div class="level-row"><span>🛑 Stop Loss</span><span id="lSL" style="color:var(--bear);">---</span><button class="copy-btn" onclick="copyVal('lSL')">Copy</button></div>
        <div class="level-row"><span>🏁 Take Profit</span><span id="lTP" style="color:var(--bull);">---</span><button class="copy-btn" onclick="copyVal('lTP')">Copy</button></div>
        <div class="level-row"><span>📐 Lot Size</span><span id="lLots">---</span></div>
        <div class="level-row"><span>📊 Risk:Reward</span><span id="lRR">---</span></div>
        <div class="level-row"><span>💵 Risk Amount</span><span id="lRisk">---</span></div>
    </div>
    
    <div class="tf-grid">
        <div class="tf-box">
            <span class="tf-label">4H STRATEGIC</span>
            <span class="tf-bias neut" id="b4h">---</span>
            <span class="tf-conf" id="c4h"></span>
            <div class="tf-detail" id="d4h"></div>
        </div>
        <div class="tf-box">
            <span class="tf-label">1H OPERATIONAL</span>
            <span class="tf-bias neut" id="b1h">---</span>
            <span class="tf-conf" id="c1h"></span>
            <div class="tf-detail" id="d1h"></div>
        </div>
        <div class="tf-box">
            <span class="tf-label">15M TACTICAL</span>
            <span class="tf-bias neut" id="b15m">---</span>
            <span class="tf-conf" id="c15m"></span>
            <div class="tf-detail" id="d15m"></div>
        </div>
    </div>
    
    <div class="ctrl-row">
        <button onclick="togglePause()" id="btnPause">⏯ Pause</button>
        <button onclick="refreshNow()">🔄 Refresh</button>
        <button onclick="stopBot()">⏹ Stop</button>
    </div>
    
    <div class="log-box"><div id="logBox"></div></div>
</div>

<div class="toast" id="toast">Copied!</div>

<script>
let timer=null,paused=false;

function log(m){const e=document.getElementById("logBox");if(!e)return;e.innerHTML+=`<div class="log-msg">${m}</div>`;e.scrollTop=e.scrollHeight;while(e.children.length>30)e.firstChild.remove()}

function showToast(){const t=document.getElementById("toast");t.classList.add("show");setTimeout(()=>t.classList.remove("show"),1500)}

function copyVal(id){const v=document.getElementById(id).textContent.replace("$","");navigator.clipboard.writeText(v).then(showToast);log("Copied: "+v)}

async function api(u,d={}){const r=await fetch(u,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(d)});return r.json()}

async function startBot(){
    const b=parseFloat(document.getElementById("balance").value)||1000;
    const r=parseFloat(document.getElementById("risk").value)||1;
    document.getElementById("setupStatus").textContent="⏳ Fetching data...";
    const d=await api("/start",{balance:b,risk:r});
    if(d.success){
        document.getElementById("setup").classList.add("hidden");
        document.getElementById("dashboard").classList.remove("hidden");
        log("✅ Bot started - Real Binance data");
        updateUI(d);
        timer=setInterval(fetchState,25000);
    }else{
        document.getElementById("setupStatus").textContent="❌ "+d.error;
    }
}

async function fetchState(){
    if(paused)return;
    const d=await api("/state");
    if(d.success)updateUI(d);
}

function updateUI(d){
    const p=d.price,s=d.signal,l=d.levels;
    document.getElementById("price").textContent="$"+p?.toFixed(2);
    document.getElementById("change").textContent=(d.change>=0?"+":"")+d.change?.toFixed(2)+"%";
    document.getElementById("change").className="price-change "+(d.change>=0?"up":"down");
    document.getElementById("cyc").textContent=d.cycles;
    
    document.getElementById("sigIcon").textContent=s?.icon||"⚪";
    document.getElementById("sigText").textContent=s?.text||"---";
    document.getElementById("sigAction").textContent=s?.action||"---";
    document.getElementById("sigConf").textContent="Confidence: "+(s?.confidence*100).toFixed(0)+"%";
    document.getElementById("sigFill").style.width=(s?.confidence*100)+"%";
    document.getElementById("sigFill").style.background=s?.confidence>.7?"var(--bull)":s?.confidence>.5?"var(--warn)":"var(--bear)";
    document.getElementById("sigReason").textContent=s?.reason||"";
    document.getElementById("sigCard").className="sig-card "+(s?.direction==="LONG"?"long":s?.direction==="SHORT"?"short":"");
    
    ["4h","1h","15m"].forEach(tf=>{
        const r=d[tf];
        document.getElementById("b"+tf).textContent=r?.bias||"---";
        document.getElementById("b"+tf).className="tf-bias "+(r?.bias==="BULLISH"?"bull":r?.bias==="BEARISH"?"bear":"neut");
        document.getElementById("c"+tf).textContent="Conf: "+(r?.confidence*100).toFixed(0)+"%";
        document.getElementById("d"+tf).textContent=r?.reason||"";
    });
    
    if(l){
        document.getElementById("levelsCard").classList.remove("hidden");
        document.getElementById("lEntry").textContent="$"+l.entry.toFixed(2);
        document.getElementById("lSL").textContent="$"+l.stop_loss.toFixed(2);
        document.getElementById("lTP").textContent="$"+l.take_profit.toFixed(2);
        document.getElementById("lLots").textContent=l.lot_size.toFixed(2);
        document.getElementById("lRR").textContent="1:"+l.risk_reward;
        document.getElementById("lRisk").textContent="$"+l.risk_amount.toFixed(2);
    }else{
        document.getElementById("levelsCard").classList.add("hidden");
    }
}

function togglePause(){paused=!paused;document.getElementById("btnPause").textContent=paused?"▶ Resume":"⏯ Pause";log(paused?"⏸ Paused":"▶ Running")}
async function refreshNow(){log("🔄 Refreshing...");const d=await api("/state");if(d.success)updateUI(d)}
function stopBot(){clearInterval(timer);document.getElementById("dashboard").classList.add("hidden");document.getElementById("setup").classList.remove("hidden");log("⏹ Stopped")}
</script>
</body>
</html>
'''

# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/start', methods=['POST'])
def start():
    data = request.json
    STATE["balance"] = float(data.get("balance", 1000))
    STATE["risk_percent"] = float(data.get("risk", 1))
    STATE["running"] = True
    STATE["paused"] = False
    
    add_log(f"🚀 Bot started | Balance: ${STATE['balance']:.0f} | Risk: {STATE['risk_percent']}%")
    
    # Run first analysis immediately
    analysis = run_full_analysis()
    
    if analysis is None:
        return jsonify({"success": False, "error": "Failed to fetch market data"})
    
    return jsonify({
        "success": True,
        "price": analysis["ticker"]["price"],
        "change": analysis["ticker"]["change"],
        "cycles": STATE["cycles"],
        "signal": analysis["signal"],
        "levels": analysis["levels"],
        "4h": analysis["strategic"],
        "1h": analysis["operational"],
        "15m": analysis["tactical"]
    })

@app.route('/state', methods=['POST'])
def get_state():
    if not STATE["running"]:
        return jsonify({"success": False, "error": "Bot not running"})
    
    if STATE["paused"]:
        # Return last analysis without running new one
        analysis = STATE.get("last_analysis")
    else:
        analysis = run_full_analysis()
    
    if analysis is None:
        return jsonify({"success": False, "error": "Analysis failed"})
    
    return jsonify({
        "success": True,
        "price": analysis["ticker"]["price"],
        "change": analysis["ticker"]["change"],
        "cycles": STATE["cycles"],
        "signal": analysis["signal"],
        "levels": analysis["levels"],
        "4h": analysis["strategic"],
        "1h": analysis["operational"],
        "15m": analysis["tactical"],
        "logs": STATE["logs"][-10:]
    })

@app.route('/logs', methods=['GET'])
def get_logs():
    return jsonify({"logs": STATE["logs"]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Market Lens Signal Bot starting on port {port}")
    app.run(host='0.0.0.0', port=port)
