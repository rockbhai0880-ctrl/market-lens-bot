import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import statistics

app = Flask(__name__)
CORS(app)

BINANCE_URL = "https://api.binance.com/api/v3/klines"

def fetch_klines(symbol, interval, limit=100):
    try:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        res = requests.get(BINANCE_URL, params=params)
        res.raise_for_status()
        data = res.json()
        klines = []
        for k in data:
            klines.append({
                "time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })
        return klines
    except Exception as e:
        print(f"Error fetching {symbol} {interval}: {e}")
        return []

def calculate_smc(klines):
    if not klines or len(klines) < 10:
        return {"bias": "NO EDGE", "confidence": 0, "fvg_count": 0, "sweep_count": 0, "ob_count": 0}
    
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    
    fvg_count = 0
    ob_count = 0
    sweep_count = 0
    
    # Simple FVG Detection
    for i in range(2, len(klines)):
        if lows[i] > highs[i-2] or highs[i] < lows[i-2]:
            fvg_count += 1
            
    # Simple OB Detection
    for i in range(1, len(klines)-1):
        if (closes[i-1] < klines[i-1]["open"] and closes[i] > klines[i]["open"] and closes[i] > highs[i-1]) or \
           (closes[i-1] > klines[i-1]["open"] and closes[i] < klines[i]["open"] and closes[i] < lows[i-1]):
            ob_count += 1
            
    # Simple Liquidity Sweep Detection
    for i in range(1, len(klines)):
        if (lows[i] < lows[i-1] and closes[i] > lows[i-1]) or (highs[i] > highs[i-1] and closes[i] < highs[i-1]):
            sweep_count += 1
            
    current_price = closes[-1]
    sma_20 = statistics.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
    
    if current_price > sma_20 and (fvg_count > 0 or ob_count > 0):
        bias = "BULLISH"
        conf = min(95, 40 + (fvg_count * 5) + (ob_count * 10))
    elif current_price < sma_20 and (fvg_count > 0 or ob_count > 0):
        bias = "BEARISH"
        conf = min(95, 40 + (fvg_count * 5) + (ob_count * 10))
    else:
        bias = "NO EDGE"
        conf = 20
        
    return {
        "bias": bias,
        "confidence": conf,
        "fvg_count": fvg_count,
        "sweep_count": sweep_count,
        "ob_count": ob_count
    }

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok", "message": "Backend SMC Engine running"})

@app.route('/api/analyze', methods=['GET'])
def analyze():
    symbol = request.args.get('symbol', 'BTCUSDT')
    
    tf_15m = fetch_klines(symbol, '15m', 200)
    tf_1h = fetch_klines(symbol, '1h', 200)
    tf_4h = fetch_klines(symbol, '4h', 200)
    
    a_15m = calculate_smc(tf_15m)
    a_1h = calculate_smc(tf_1h)
    a_4h = calculate_smc(tf_4h)
    
    b_4h, b_1h, b_15m = a_4h["bias"], a_1h["bias"], a_15m["bias"]
    
    if b_4h == "BULLISH" and b_1h == "BULLISH" and b_15m == "BULLISH":
        signal, color = "STRONG LONG", "success"
    elif b_4h == "BEARISH" and b_1h == "BEARISH" and b_15m == "BEARISH":
        signal, color = "STRONG SHORT", "danger"
    elif b_4h == "BULLISH" and b_1h == "BULLISH":
        signal, color = "BULLISH BIAS", "warning"
    elif b_4h == "BEARISH" and b_1h == "BEARISH":
        signal, color = "BEARISH BIAS", "warning"
    elif b_4h == "BULLISH":
        signal, color = "BACKGROUND BULLISH", "neutral"
    elif b_4h == "BEARISH":
        signal, color = "BACKGROUND BEARISH", "neutral"
    else:
        signal, color = "NO EDGE", "neutral"
        
    avg_conf = (a_4h["confidence"] + a_1h["confidence"] + a_15m["confidence"]) // 3
    
    return jsonify({
        "symbol": symbol,
        "final_signal": signal,
        "color_theme": color,
        "overall_confidence": avg_conf,
        "timeframes": {"15m": a_15m, "1h": a_1h, "4h": a_4h}
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
