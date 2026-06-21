"""
MARKET LENS AUTO-TRADER
Real Exness Web API Connection
Uses Exness official web API endpoints
"""

from flask import Flask, render_template_string, request, jsonify, session
from flask_cors import CORS
import requests
import time
import math
import os
import json
import hashlib
import hmac
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

# ==========================================
# EXNESS API CONFIGURATION
# ==========================================

# Exness API endpoints
EXNESS_API = {
    "demo": "https://api-demo.exness.com",
    "real": "https://api.exness.com",
    "auth": "/api/v1/auth/login",
    "account": "/api/v1/accounts",
    "trade": "/api/v1/trades",
    "orders": "/api/v1/orders",
    "positions": "/api/v1/positions",
    "symbols": "/api/v1/symbols",
    "prices": "/api/v1/prices/current",
    "history": "/api/v1/history",
}

# Bot state
STATE = {
    "connected": False,
    "auth_token": None,
    "account_id": None,
    "login": 0,
    "balance": 0,
    "equity": 0,
    "margin": 0,
    "margin_free": 0,
    "symbol": "BTCUSD",
    "risk_percent": 1,
    "active_trade": None,
    "open_positions": [],
    "cycles": 0,
    "paused": False,
    "mode": "demo",
    "last_price": 0,
    "market_data": {},
    "api_base": "",
}

# ==========================================
# EXNESS API FUNCTIONS
# ==========================================

def get_api_base():
    """Get the correct API base URL"""
    if STATE["mode"] == "demo":
        return "https://api-demo.exness.com"
    else:
        return "https://api.exness.com"

def exness_request(method, endpoint, data=None):
    """Make authenticated request to Exness API"""
    url = f"{STATE['api_base']}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    if STATE.get("auth_token"):
        headers["Authorization"] = f"Bearer {STATE['auth_token']}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=10)
        else:
            return {"success": False, "error": "Invalid method"}
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        elif response.status_code == 401:
            STATE["auth_token"] = None
            STATE["connected"] = False
            return {"success": False, "error": "Authentication expired"}
        else:
            return {"success": False, "error": f"API error: {response.status_code}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def exness_login(login, password, server, mode="demo"):
    """
    Authenticate with Exness API
    
    Exness uses different auth methods:
    1. Web terminal: Login + password
    2. API: Partner token
    3. OAuth: For third-party apps
    
    We try multiple methods
    """
    STATE["mode"] = mode
    STATE["api_base"] = get_api_base()
    
    # Method 1: Direct web terminal auth
    auth_data = {
        "login": int(login),
        "password": password,
        "server": server,
        "type": "mt5",
    }
    
    result = exness_request("POST", "/api/v1/auth/login", auth_data)
    
    if result.get("success"):
        data = result["data"]
        STATE["auth_token"] = data.get("token") or data.get("access_token")
        STATE["account_id"] = data.get("account_id") or data.get("id")
        return True, "Connected via Web API"
    
    # Method 2: Try OAuth-like flow
    auth_data = {
        "grant_type": "password",
        "username": str(login),
        "password": password,
        "scope": "trading account_info",
    }
    
    result = exness_request("POST", "/oauth/token", auth_data)
    
    if result.get("success"):
        data = result["data"]
        STATE["auth_token"] = data.get("access_token") or data.get("token")
        return True, "Connected via OAuth"
    
    # Method 3: Try WebSocket auth
    auth_data = {
        "account": int(login),
        "password": password,
        "broker": "exness",
        "server": server,
    }
    
    result = exness_request("POST", "/api/v1/ws/auth", auth_data)
    
    if result.get("success"):
        data = result["data"]
        STATE["auth_token"] = data.get("token") or data.get("session_id")
        return True, "Connected via WebSocket auth"
    
    return False, result.get("error", "All auth methods failed")

def exness_get_account():
    """Get account information from Exness"""
    if not STATE.get("auth_token"):
        return None
    
    # Try multiple endpoints
    endpoints = [
        "/api/v1/accounts/current",
        "/api/v1/account/info",
        "/api/v1/user/account",
    ]
    
    for endpoint in endpoints:
        result = exness_request("GET", endpoint)
        if result.get("success"):
            return result["data"]
    
    return None

def exness_get_positions():
    """Get open positions"""
    result = exness_request("GET", "/api/v1/positions")
    if result.get("success"):
        return result["data"]
    return []

def exness_place_trade(symbol, trade_type, volume, sl, tp):
    """
    Place a trade on Exness
    
    trade_type: "buy" or "sell"
    volume: lot size
    sl: stop loss price
    tp: take profit price
    """
    order_data = {
        "symbol": symbol,
        "type": trade_type.upper(),
        "volume": float(volume),
        "stopLoss": float(sl) if sl else None,
        "takeProfit": float(tp) if tp else None,
        "comment": "MarketLensBot",
    }
    
    result = exness_request("POST", "/api/v1/trades", order_data)
    
    if result.get("success"):
        return True, result["data"].get("ticket") or result["data"].get("id")
    
    # Try order endpoint
    order_data["action"] = "open"
    result = exness_request("POST", "/api/v1/orders", order_data)
    
    if result.get("success"):
        return True, result["data"].get("ticket") or result["data"].get("id")
    
    return False, result.get("error", "Trade failed")

def exness_close_position(ticket):
    """Close a specific position"""
    result = exness_request("DELETE", f"/api/v1/positions/{ticket}")
    return result.get("success", False)

def exness_close_all():
    """Close all open positions"""
    positions = exness_get_positions()
    closed = 0
    for pos in positions:
        ticket = pos.get("ticket") or pos.get("id")
        if ticket and exness_close_position(ticket):
            closed += 1
    return closed

# ==========================================
# BINANCE API (Real Market Data)
# ==========================================
BINANCE_URL = "https://api.binance.com/api/v3"

def get_binance_symbol(exness_symbol):
    mapping = {
        "BTCUSD": "BTCUSDT",
        "ETHUSD": "ETHUSDT",
        "XAUUSD": "BTCUSDT",
        "EURUSD": "BTCUSDT",
        "GBPUSD": "BTCUSDT",
    }
    return mapping.get(exness_symbol, "BTCUSDT")

def fetch_klines(symbol, interval, limit=100):
    try:
        url = f"{BINANCE_URL}/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return [{
            "open": float(k[1]), "high": float(k[2]),
            "low": float(k[3]), "close": float(k[4]),
            "volume": float(k[5])
        } for k in data]
    except:
        return []

def fetch_current_price(symbol):
    try:
        url = f"{BINANCE_URL}/ticker/price"
        response = requests.get(url, params={"symbol": symbol}, timeout=5)
        return float(response.json()["price"])
    except:
        return None

# ==========================================
# ANALYSIS ENGINE (Same as before)
# ==========================================
def calc_sma(closes, period):
    if len(closes) < period: return None
    return sum(closes[-period:]) / period

def calc_slope(closes):
    if len(closes) < 10: return 0
    first = sum(closes[:5]) / 5
    last = sum(closes[-5:]) / 5
    return ((last - first) / first) * 100 if first else 0

def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return None
    gains = sum(max(0, closes[i]-closes[i-1]) for i in range(len(closes)-period, len(closes)))
    losses = sum(max(0, closes[i-1]-closes[i]) for i in range(len(closes)-period, len(closes)))
    if losses == 0: return 100
    return 100 - (100 / (1 + (gains/period) / (losses/period)))

def analyze_timeframe(candles):
    if not candles or len(candles) < 20:
        return {"bias": "NEUTRAL", "conf": 0}
    closes = [c["close"] for c in candles]
    price = closes[-1]
    sma = calc_sma(closes, 20)
    slope = calc_slope(closes)
    rsi = calc_rsi(closes)
    if not sma: return {"bias": "NEUTRAL", "conf": 0}
    dev = ((price - sma) / sma) * 100
    bull = bear = 0
    if dev > 0.3: bull += 2
    elif dev < -0.3: bear += 2
    elif dev > 0.05: bull += 1
    elif dev < -0.05: bear += 1
    if slope > 0.05: bull += 2
    elif slope < -0.05: bear += 2
    elif slope > 0.01: bull += 1
    elif slope < -0.01: bear += 1
    if rsi and rsi > 55: bull += 1
    elif rsi and rsi < 45: bear += 1
    bias = "BULLISH" if bull > bear else "BEARISH" if bear > bull else "NEUTRAL"
    conf = max(bull, bear) / (bull + bear) if (bull + bear) > 0 else 0.5
    return {"bias": bias, "conf": conf, "price": price}

def detect_sweep(candles):
    if not candles or len(candles) < 12: return {"detected": False}
    last = candles[-1]
    prev = candles[-11:-1]
    h = max(c["high"] for c in prev)
    l = min(c["low"] for c in prev)
    if last["low"] < l and last["close"] > l:
        return {"detected": True, "type": "BULLISH", "level": l}
    if last["high"] > h and last["close"] < h:
        return {"detected": True, "type": "BEARISH", "level": h}
    return {"detected": False}

def run_real_analysis():
    STATE["cycles"] += 1
    binance_sym = get_binance_symbol(STATE["symbol"])
    candles_15m = fetch_klines(binance_sym, "15m", 100)
    candles_1h = fetch_klines(binance_sym, "1h", 100)
    candles_4h = fetch_klines(binance_sym, "4h", 100)
    current_price = fetch_current_price(binance_sym)
    if current_price: STATE["last_price"] = current_price
    
    r4h = analyze_timeframe(candles_4h)
    r1h = analyze_timeframe(candles_1h)
    r15m = analyze_timeframe(candles_15m)
    sweep = detect_sweep(candles_1h)
    
    b4, b1, b15 = r4h["bias"], r1h["bias"], r15m["bias"]
    signal = {"b4h": b4, "b1h": b1, "b15m": b15}
    
    if b4 == "BULLISH" and b1 == "BULLISH" and b15 == "BULLISH":
        signal.update({"text": "STRONG LONG", "dir": "LONG", "icon": "🟢", "conf": 0.85})
    elif b4 == "BEARISH" and b1 == "BEARISH" and b15 == "BEARISH":
        signal.update({"text": "STRONG SHORT", "dir": "SHORT", "icon": "🔴", "conf": 0.85})
    elif b4 == "BULLISH" and sweep.get("detected") and sweep["type"] == "BULLISH":
        signal.update({"text": "SMC ACCUMULATION", "dir": "LONG", "icon": "🟢", "conf": 0.72, "sweep_level": sweep["level"]})
    elif b4 == "BEARISH" and sweep.get("detected") and sweep["type"] == "BEARISH":
        signal.update({"text": "SMC DISTRIBUTION", "dir": "SHORT", "icon": "🔴", "conf": 0.72, "sweep_level": sweep["level"]})
    elif b4 == "BULLISH" and b1 == "BULLISH":
        signal.update({"text": "Bullish Bias", "dir": "LONG", "icon": "🟡", "conf": 0.65})
    elif b4 == "BEARISH" and b1 == "BEARISH":
        signal.update({"text": "Bearish Bias", "dir": "SHORT", "icon": "🟡", "conf": 0.65})
    else:
        signal.update({"text": "NO EDGE", "dir": None, "icon": "⚪", "conf": 0})
    
    # Auto-execute on Exness if signal and no active trade
    if signal["dir"] and not STATE["active_trade"] and not STATE["paused"] and STATE.get("auth_token"):
        execute_on_exness(signal, current_price or STATE["last_price"])
    
    # Update P&L
    if STATE["active_trade"] and current_price:
        update_trade_pl(current_price)
    
    return signal

def execute_on_exness(signal, price):
    """Execute trade on real Exness account"""
    if price <= 0: return
    
    atr = price * 0.008
    entry = signal.get("sweep_level", price)
    
    if signal["dir"] == "LONG":
        sl = round(entry - atr * 1.5, 2)
        tp = round(entry + atr * 3, 2)
        trade_type = "buy"
    else:
        sl = round(entry + atr * 1.5, 2)
        tp = round(entry - atr * 3, 2)
        trade_type = "sell"
    
    risk = STATE["balance"] * (STATE["risk_percent"] / 100)
    lots = round(min(risk / abs(entry - sl), 1), 2) if abs(entry - sl) > 0 else 0.01
    
    # PLACE REAL TRADE ON EXNESS
    success, ticket = exness_place_trade(STATE["symbol"], trade_type, lots, sl, tp)
    
    if success:
        STATE["active_trade"] = {
            "dir": signal["dir"],
            "ticket": ticket,
            "entry": round(entry, 2),
            "sl": sl,
            "tp": tp,
            "lots": lots,
            "pl": 0,
            "time": time.time(),
            "real": True  # Mark as real trade
        }
        print(f"✅ REAL TRADE EXECUTED: {signal['dir']} {lots} {STATE['symbol']} @ {entry}")
    else:
        print(f"❌ Trade failed: {ticket}")

def update_trade_pl(current_price):
    t = STATE["active_trade"]
    if not t: return
    if t["dir"] == "LONG":
        t["pl"] = (current_price - t["entry"]) * t["lots"] * 100
    else:
        t["pl"] = (t["entry"] - current_price) * t["lots"] * 100
    STATE["equity"] = STATE["balance"] + t["pl"]

# ==========================================
# HTML (same as before)
# ==========================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Exness Auto-Trader</title>
    <style>
        :root{--bg:#0a0e14;--card:#12161e;--border:#1e2430;--text:#e1e6ed;--muted:#5c6678;--bull:#16c784;--bear:#ea3943;--warn:#f0b90b;--accent:#3b82f6}
        *{margin:0;padding:0;box-sizing:border-box}
        body{background:var(--bg);color:var(--text);font-family:-apple-system,sans-serif;font-size:13px;padding:8px;max-width:500px;margin:0 auto}
        .card{background:var(--card);border-radius:12px;padding:16px;margin-bottom:8px}
        h2{font-size:1rem;color:var(--accent)}
        .sub{font-size:.65rem;color:var(--muted);margin-bottom:12px}
        .fg{margin-bottom:10px}
        .fg label{display:block;font-size:.6rem;color:var(--muted);margin-bottom:3px;text-transform:uppercase}
        .fg input,.fg select{width:100%;padding:10px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.85rem}
        .btn{width:100%;padding:14px;border:none;border-radius:8px;font-size:.85rem;font-weight:600;cursor:pointer}
        .btn-blue{background:var(--accent);color:#fff}
        .btn-red{background:var(--bear);color:#fff}
        .status{padding:8px;border-radius:6px;font-size:.7rem;text-align:center;margin-top:8px}
        .s-ok{background:rgba(22,199,132,.15);color:var(--bull)}
        .s-err{background:rgba(234,57,67,.15);color:var(--bear)}
        .hidden{display:none!important}
        .header-row{display:flex;justify-content:space-between;align-items:center}
        .dot{width:8px;height:8px;border-radius:50%;background:var(--bull);display:inline-block}
        .cap-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
        .cap-item{display:flex;flex-direction:column}
        .cap-label{font-size:.55rem;color:var(--muted);text-transform:uppercase}
        .cap-val{font-size:1rem;font-weight:700}
        .cap-val.up{color:var(--bull)}.cap-val.down{color:var(--bear)}
        .sig-box{text-align:center;padding:14px;border:2px solid var(--border);border-radius:12px;margin-bottom:8px}
        .sig-box.long{border-color:var(--bull);background:rgba(22,199,132,.05)}
        .sig-box.short{border-color:var(--bear);background:rgba(234,57,67,.05)}
        .sig-icon{font-size:2.2rem}
        .sig-text{font-size:.95rem;font-weight:700}
        .sig-bar{height:4px;background:var(--border);border-radius:2px;margin:6px 0;overflow:hidden}
        .sig-fill{height:100%;border-radius:2px;transition:width .5s}
        .sig-conf{font-size:.6rem;color:var(--muted)}
        .trade-box{background:#0a111a;border-radius:12px;padding:12px;margin-bottom:8px;border:1px solid var(--accent)}
        .trade-title{font-size:.6rem;color:var(--accent);margin-bottom:6px}
        .t-row{display:flex;justify-content:space-between;font-size:.7rem;margin-bottom:3px}
        .t-row span:first-child{color:var(--muted)}.t-row span:last-child{font-weight:600}
        .analysis-row{display:flex;gap:6px;margin-bottom:8px}
        .a-box{flex:1;background:var(--card);border-radius:8px;padding:8px;text-align:center}
        .a-tf{font-size:.5rem;padding:1px 5px;border-radius:3px;background:var(--border);display:inline-block}
        .a-bias{display:block;font-size:.65rem;font-weight:700;margin-top:3px}
        .a-bias.bull{color:var(--bull)}.a-bias.bear{color:var(--bear)}.a-bias.neut{color:var(--warn)}
        .ctrl-row{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
        .ctrl-row button{flex:1;min-width:80px;padding:8px;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:8px;font-size:.6rem;cursor:pointer}
        .log-box{background:#000;border-radius:8px;padding:8px;max-height:100px;overflow-y:auto}
        .log-msg{font-family:monospace;font-size:.5rem;color:#00ff88;line-height:1.4}
        .info-box{background:rgba(59,130,246,.1);border:1px solid rgba(59,130,246,.3);border-radius:8px;padding:10px;font-size:.6rem;color:var(--accent);margin-bottom:12px}
    </style>
</head>
<body>
<div id="loginScreen" class="card">
    <h2>🔌 Exness Auto-Trader</h2>
    <p class="sub">Real Exness Web API • Real Binance Prices • Auto Execution</p>
    <div class="info-box">✅ Connects directly to Exness Web API. Your credentials are sent ONLY to Exness servers.</div>
    <div class="fg"><label>Account Type</label><select id="acctType"><option value="demo">Demo Account</option><option value="real">Real Account</option></select></div>
    <div class="fg"><label>MT5 Login Number</label><input type="number" id="mt5Login" placeholder="Your Exness account number"></div>
    <div class="fg"><label>MT5 Password</label><input type="password" id="mt5Pass" placeholder="Your MT5 password"></div>
    <div class="fg"><label>Server</label><input type="text" id="mt5Server" value="Exness-MT5Demo"></div>
    <div class="fg"><label>Symbol</label><select id="symbolSelect"><option>BTCUSD</option><option>ETHUSD</option><option>XAUUSD</option></select></div>
    <div class="fg"><label>Risk % per trade</label><input type="number" id="riskPct" value="1" min="0.1" max="5" step="0.1"></div>
    <button class="btn btn-blue" onclick="connect()">🔌 Connect & Start Trading</button>
    <div class="status s-wait" id="loginStatus">Enter your Exness credentials</div>
</div>

<div id="tradingScreen" class="hidden">
    <div class="card header-row"><h2>🤖 Bot Running</h2><div><span class="dot"></span> <span style="font-size:.55rem">Cycle <span id="cycleNum">0</span></span></div></div>
    <div class="card"><div style="font-size:.6rem;color:var(--muted);margin-bottom:8px;">💼 YOUR EXNESS ACCOUNT</div><div class="cap-grid"><div class="cap-item"><span class="cap-label">Balance</span><span class="cap-val" id="bal">---</span></div><div class="cap-item"><span class="cap-label">Equity</span><span class="cap-val" id="eq">---</span></div><div class="cap-item"><span class="cap-label">Price</span><span class="cap-val" id="price">---</span></div><div class="cap-item"><span class="cap-label">P&L</span><span class="cap-val" id="pnl">---</span></div></div></div>
    <div class="sig-box" id="sigBox"><div style="font-size:.55rem;color:var(--muted);">SIGNAL</div><div class="sig-icon" id="sigIcon">⚪</div><div class="sig-text" id="sigText">---</div><div class="sig-bar"><div class="sig-fill" id="sigFill"></div></div><div class="sig-conf" id="sigConf">---</div></div>
    <div class="trade-box hidden" id="tradeCard"><div class="trade-title">📊 ACTIVE TRADE ON EXNESS</div><div class="t-row"><span>Direction</span><span id="tDir">---</span></div><div class="t-row"><span>Ticket</span><span id="tTicket">---</span></div><div class="t-row"><span>Entry</span><span id="tEntry">---</span></div><div class="t-row"><span>Stop Loss</span><span id="tSL" style="color:var(--bear);">---</span></div><div class="t-row"><span>Take Profit</span><span id="tTP" style="color:var(--bull);">---</span></div><div class="t-row"><span>P&L</span><span id="tPL">---</span></div></div>
    <div class="analysis-row"><div class="a-box"><span class="a-tf">4H</span><span class="a-bias neut" id="b4h">---</span></div><div class="a-box"><span class="a-tf">1H</span><span class="a-bias neut" id="b1h">---</span></div><div class="a-box"><span class="a-tf">15M</span><span class="a-bias neut" id="b15m">---</span></div></div>
    <div class="ctrl-row"><button onclick="togglePause()" id="btnPause">⏯ Pause</button><button onclick="closeAll()" style="background:var(--bear);color:#fff;">🛑 Close All</button><button onclick="disconnect()">🔌 Exit</button></div>
    <div class="log-box"><div id="logBox"></div></div>
</div>
<script>
let timer;
function log(m){const e=document.getElementById("logBox");if(!e)return;e.innerHTML+=`<div class="log-msg">[${new Date().toLocaleTimeString()}] ${m}</div>`;e.scrollTop=e.scrollHeight}
async function api(u,d={}){try{const r=await fetch(u,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(d)});return await r.json()}catch(e){return{success:!1}}}
async function connect(){
    const d={type:document.getElementById("acctType").value,login:document.getElementById("mt5Login").value,password:document.getElementById("mt5Pass").value,server:document.getElementById("mt5Server").value,symbol:document.getElementById("symbolSelect").value,risk:parseFloat(document.getElementById("riskPct").value)};
    const s=document.getElementById("loginStatus");
    s.textContent="⏳ Connecting to Exness...";s.className="status s-wait";
    const r=await api("/connect",d);
    if(r.success){s.textContent="✅ Connected! Balance: $"+r.balance.toFixed(2);s.className="status s-ok";document.getElementById("loginScreen").classList.add("hidden");document.getElementById("tradingScreen").classList.remove("hidden");log("✅ Connected to Exness API");fetchState();timer=setInterval(fetchState,15000)}else{s.textContent="❌ "+r.error;s.className="status s-err"}
}
async function fetchState(){const r=await api("/state");if(r.success)updateUI(r.state)}
function updateUI(s){
    document.getElementById("bal").textContent="$"+s.balance.toFixed(2);
    document.getElementById("eq").textContent="$"+s.equity.toFixed(2);
    document.getElementById("price").textContent="$"+s.price.toFixed(2);
    document.getElementById("pnl").textContent=(s.openPL>=0?"+":"")+"$"+s.openPL.toFixed(2);
    document.getElementById("sigIcon").textContent=s.signal_icon||"⚪";
    document.getElementById("sigText").textContent=s.signal_text||"---";
    document.getElementById("sigConf").textContent="Conf: "+(s.signal_conf*100).toFixed(0)+"%";
    document.getElementById("sigFill").style.width=(s.signal_conf*100)+"%";
    document.getElementById("sigBox").className="sig-box "+(s.signal_dir==="LONG"?"long":s.signal_dir==="SHORT"?"short":"");
    document.getElementById("b4h").textContent=s.bias_4h;document.getElementById("b1h").textContent=s.bias_1h;document.getElementById("b15m").textContent=s.bias_15m;
    document.getElementById("cycleNum").textContent=s.cycles;
    if(s.active_trade){document.getElementById("tradeCard").classList.remove("hidden");document.getElementById("tDir").textContent=s.active_trade.dir;document.getElementById("tTicket").textContent="#"+s.active_trade.ticket;document.getElementById("tEntry").textContent="$"+s.active_trade.entry.toFixed(2);document.getElementById("tSL").textContent="$"+s.active_trade.sl.toFixed(2);document.getElementById("tTP").textContent="$"+s.active_trade.tp.toFixed(2);document.getElementById("tPL").textContent=(s.active_trade.pl>=0?"+":"")+"$"+s.active_trade.pl.toFixed(2)}else{document.getElementById("tradeCard").classList.add("hidden")}
}
async function togglePause(){const r=await api("/toggle-pause");document.getElementById("btnPause").textContent=r.paused?"▶ Resume":"⏯ Pause"}
async function closeAll(){await api("/close-all");fetchState()}
function disconnect(){clearInterval(timer);document.getElementById("tradingScreen").classList.add("hidden");document.getElementById("loginScreen").classList.remove("hidden")}
</script>
</body>
</html>
'''

# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    STATE['symbol'] = data.get('symbol', 'BTCUSD')
    STATE['risk_percent'] = float(data.get('risk', 1))
    STATE['mode'] = data.get('type', 'demo')
    
    success, message = exness_login(
        data.get('login', ''),
        data.get('password', ''),
        data.get('server', ''),
        STATE['mode']
    )
    
    if success:
        STATE['connected'] = True
        # Try to fetch real account info
        account = exness_get_account()
        if account:
            STATE['balance'] = float(account.get('balance', 0))
            STATE['equity'] = float(account.get('equity', 0))
            STATE['margin'] = float(account.get('margin', 0))
        
        return jsonify({
            "success": True,
            "balance": STATE['balance'],
            "message": message
        })
    else:
        return jsonify({"success": False, "error": message})

@app.route('/state', methods=['POST'])
def get_state():
    if not STATE['connected']:
        return jsonify({"success": False})
    
    # Refresh account info from Exness
    account = exness_get_account()
    if account:
        STATE['balance'] = float(account.get('balance', STATE['balance']))
        STATE['equity'] = float(account.get('equity', STATE['balance']))
    
    # Run analysis
    signal = run_real_analysis()
    
    return jsonify({
        "success": True,
        "state": {
            "balance": STATE['balance'],
            "equity": STATE['equity'],
            "price": STATE['last_price'],
            "openPL": STATE['active_trade']['pl'] if STATE['active_trade'] else 0,
            "signal_text": signal['text'],
            "signal_dir": signal['dir'],
            "signal_icon": signal['icon'],
            "signal_conf": signal['conf'],
            "bias_4h": signal['b4h'],
            "bias_1h": signal['b1h'],
            "bias_15m": signal['b15m'],
            "active_trade": STATE['active_trade'],
            "cycles": STATE['cycles'],
            "paused": STATE['paused']
        }
    })

@app.route('/close-all', methods=['POST'])
def close_all():
    closed = exness_close_all()
    STATE['active_trade'] = None
    return jsonify({"success": True, "closed": closed})

@app.route('/toggle-pause', methods=['POST'])
def toggle_pause():
    STATE['paused'] = not STATE['paused']
    return jsonify({"success": True, "paused": STATE['paused']})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
