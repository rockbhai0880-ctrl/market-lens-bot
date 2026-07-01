"""
CONFIGURATION FILE
Replace these values with your actual Exness MT5 credentials
"""

# ============================================
# EXNESS / MT5 ACCOUNT CREDENTIALS
# ============================================
MT5_ACCOUNT = 12345678           # Your Exness account number
MT5_PASSWORD = "your_password"   # Your Exness MT5 password
MT5_SERVER = "Exness-MT5Trial"   # Demo: "Exness-MT5Trial" | Live: "Exness-Real"

# ============================================
# TRADING SETTINGS
# ============================================
SYMBOL = "EURUSD"                # Currency pair to trade
TIMEFRAME = "M1"                 # M1 = 1-minute candles
MAX_BARS = 200                   # Number of candles to analyze

# ============================================
# RISK MANAGEMENT
# ============================================
RISK_PER_TRADE = 0.02            # 2% of account balance per trade
MAX_DAILY_LOSS_PCT = 0.10        # 10% max daily loss (bot stops)
MAX_CONSECUTIVE_LOSSES = 6       # Circuit breaker threshold
COOLDOWN_MINUTES = 30            # Pause duration after circuit breaker
STOP_LOSS_PIPS = 20              # Stop loss in pips
TAKE_PROFIT_PIPS = 40            # Take profit in pips (1:2 risk-reward)
MAX_SPREAD_PIPS = 3              # Don't trade if spread > this

# ============================================
# STRATEGY PARAMETERS
# ============================================
SMA_FAST = 5                     # Fast moving average period
SMA_SLOW = 20                    # Slow moving average period
EMA_FAST = 5                     # Fast exponential MA
EMA_SLOW = 20                    # Slow exponential MA
RSI_PERIOD = 7                   # RSI period
RSI_LOWER = 35                   # RSI oversold threshold
RSI_UPPER = 65                   # RSI overbought threshold
ADX_PERIOD = 14                  # ADX period
ADX_THRESHOLD = 25               # Minimum ADX for trending market
MACD_FAST = 12                   # MACD fast EMA
MACD_SLOW = 26                   # MACD slow EMA
MACD_SIGNAL = 9                  # MACD signal line
BB_PERIOD = 20                   # Bollinger Bands period
BB_STD = 2                       # Bollinger Bands standard deviation
MIN_SIGNAL_SCORE = 6             # Minimum score to trigger BUY (out of 8)

# ============================================
# SESSION FILTER (GMT Times)
# ============================================
TRADE_LONDON_OPEN = True         # 07:00-09:00 GMT
TRADE_LONDON_NY_OVERLAP = True   # 12:00-16:00 GMT
TRADE_ASIAN = False              # Usually low volatility
TRADE_FRIDAY_AFTERNOON = False   # Often unpredictable
