"""
AUTONOMOUS AI FOREX TRADING BOT
================================
Connects to Exness via MetaTrader 5
Analyzes market using multiple technical indicators
Executes trades automatically with full risk management

Author: AI Trading System
Version: 2.0
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, time
import time as time_module
import sys
import json
from pathlib import Path

# Import configuration
try:
    from config import *
except ImportError:
    print("ERROR: config.py not found. Create it from the template.")
    sys.exit(1)

# ============================================
# LOGGING SYSTEM
# ============================================
class Logger:
    """Simple logger with file output"""
    def __init__(self):
        self.log_file = Path("bot_log.txt")
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        print(formatted)
        with open(self.log_file, "a") as f:
            f.write(formatted + "\n")

logger = Logger()

# ============================================
# MT5 CONNECTION MANAGER
# ============================================
class MT5Connection:
    """Handles MetaTrader 5 connection and authentication"""
    
    def __init__(self):
        self.connected = False
        self.account_info = None
    
    def connect(self):
        """Connect to Exness MT5 terminal"""
        logger.log("Connecting to MetaTrader 5...")
        
        if not mt5.initialize():
            error = mt5.last_error()
            logger.log(f"MT5 initialization failed: {error}", "ERROR")
            return False
        
        logger.log(f"Logging in to account {MT5_ACCOUNT} on {MT5_SERVER}...")
        
        authorized = mt5.login(
            login=MT5_ACCOUNT,
            password=MT5_PASSWORD,
            server=MT5_SERVER
        )
        
        if not authorized:
            error = mt5.last_error()
            logger.log(f"Login failed: {error}", "ERROR")
            mt5.shutdown()
            return False
        
        self.account_info = mt5.account_info()
        if self.account_info is None:
            logger.log("Failed to get account info", "ERROR")
            return False
        
        self.connected = True
        logger.log(f"✅ Connected successfully!")
        logger.log(f"   Account: {self.account_info.login}")
        logger.log(f"   Balance: ${self.account_info.balance:.2f}")
        logger.log(f"   Equity: ${self.account_info.equity:.2f}")
        logger.log(f"   Leverage: 1:{self.account_info.leverage}")
        return True
    
    def disconnect(self):
        """Disconnect from MT5"""
        mt5.shutdown()
        self.connected = False
        logger.log("Disconnected from MT5")
    
    def get_balance(self):
        """Get current account balance"""
        if not self.connected:
            return 0
        info = mt5.account_info()
        return info.balance if info else 0
    
    def get_equity(self):
        """Get current account equity"""
        if not self.connected:
            return 0
        info = mt5.account_info()
        return info.equity if info else 0

# ============================================
# MARKET DATA ENGINE
# ============================================
class MarketData:
    """Fetches and processes market data"""
    
    def __init__(self, connection):
        self.connection = connection
    
    def get_candles(self, symbol=SYMBOL, bars=MAX_BARS):
        """Fetch recent candle data"""
        # Map string timeframe to MT5 constant
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        tf = timeframe_map.get(TIMEFRAME, mt5.TIMEFRAME_M1)
        
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
        
        if rates is None or len(rates) < 50:
            logger.log(f"Failed to get data for {symbol}. Check symbol name.", "WARNING")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df
    
    def get_current_price(self, symbol=SYMBOL):
        """Get current bid/ask prices"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None, None
        return tick.bid, tick.ask
    
    def get_spread(self, symbol=SYMBOL):
        """Get current spread in pips"""
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if tick is None or info is None:
            return 999
        spread = (tick.ask - tick.bid) / info.point
        return int(spread)
    
    def is_market_open(self, symbol=SYMBOL):
        """Check if market is open for trading"""
        info = mt5.symbol_info(symbol)
        if info is None:
            return False
        return info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL

# ============================================
# TECHNICAL ANALYSIS ENGINE
# ============================================
class TechnicalAnalysis:
    """Calculates all technical indicators"""
    
    @staticmethod
    def add_all_indicators(df):
        """Add all indicators to dataframe"""
        if df is None or len(df) < 50:
            return df
        
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Simple Moving Averages
        df['SMA_FAST'] = close.rolling(window=SMA_FAST).mean()
        df['SMA_SLOW'] = close.rolling(window=SMA_SLOW).mean()
        
        # Exponential Moving Averages
        df['EMA_FAST'] = close.ewm(span=EMA_FAST, adjust=False).mean()
        df['EMA_SLOW'] = close.ewm(span=EMA_SLOW, adjust=False).mean()
        
        # MACD
        ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
        ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
        df['MACD'] = ema_fast - ema_slow
        df['MACD_SIGNAL'] = df['MACD'].ewm(span=MACD_SIGNAL, adjust=False).mean()
        df['MACD_HIST'] = df['MACD'] - df['MACD_SIGNAL']
        
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=RSI_PERIOD).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # ADX
        df['TR'] = np.maximum(
            high - low,
            np.maximum(
                abs(high - close.shift()),
                abs(low - close.shift())
            )
        )
        df['ATR'] = df['TR'].rolling(window=ADX_PERIOD).mean()
        
        plus_dm = np.where((high - high.shift()) > (low.shift() - low),
                          np.maximum(high - high.shift(), 0), 0)
        minus_dm = np.where((low.shift() - low) > (high - high.shift()),
                           np.maximum(low.shift() - low, 0), 0)
        
        df['+DI'] = 100 * (pd.Series(plus_dm).rolling(window=ADX_PERIOD).mean() / df['ATR'])
        df['-DI'] = 100 * (pd.Series(minus_dm).rolling(window=ADX_PERIOD).mean() / df['ATR'])
        df['DX'] = 100 * abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])
        df['ADX'] = df['DX'].rolling(window=ADX_PERIOD).mean()
        
        # Bollinger Bands
        df['BB_MIDDLE'] = close.rolling(window=BB_PERIOD).mean()
        bb_std = close.rolling(window=BB_PERIOD).std()
        df['BB_UPPER'] = df['BB_MIDDLE'] + (BB_STD * bb_std)
        df['BB_LOWER'] = df['BB_MIDDLE'] - (BB_STD * bb_std)
        df['BB_WIDTH'] = df['BB_UPPER'] - df['BB_LOWER']
        df['BB_WIDTH_PCT'] = (df['BB_WIDTH'] / df['BB_MIDDLE']) * 100
        
        # Volume indicators (optional)
        df['Volume_SMA'] = df['tick_volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['tick_volume'] / df['Volume_SMA']
        
        return df

# ============================================
# AI SIGNAL ENGINE
# ============================================
class SignalEngine:
    """The brain - generates trading signals based on multiple conditions"""
    
    def __init__(self):
        self.last_signal = "HOLD"
        self.signal_history = []
    
    def analyze(self, df):
        """
        Analyze market and return signal
        Returns: 'BUY', 'SELL', or 'HOLD'
        """
        if df is None or len(df) < 50:
            return "HOLD", 0
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        score = 0
        reasons = []
        
        # ============================================
        # CONDITION 1: Price above slow MA (Trend)
        # ============================================
        if latest['close'] > latest['SMA_SLOW']:
            score += 1
            reasons.append("Price > SMA_SLOW")
        
        # ============================================
        # CONDITION 2: Fast MA above slow MA (Trend structure)
        # ============================================
        if latest['SMA_FAST'] > latest['SMA_SLOW']:
            score += 1
            reasons.append("SMA_FAST > SMA_SLOW")
        
        # ============================================
        # CONDITION 3: EMA crossover bullish
        # ============================================
        if latest['EMA_FAST'] > latest['EMA_SLOW']:
            score += 1
            reasons.append("EMA_FAST > EMA_SLOW")
        
        # ============================================
        # CONDITION 4: MACD above zero (Momentum)
        # ============================================
        if latest['MACD'] > 0:
            score += 1
            reasons.append("MACD > 0")
        
        # ============================================
        # CONDITION 5: MACD above signal line
        # ============================================
        if latest['MACD'] > latest['MACD_SIGNAL']:
            score += 1
            reasons.append("MACD > Signal")
        
        # ============================================
        # CONDITION 6: RSI in healthy range
        # ============================================
        if RSI_LOWER < latest['RSI'] < RSI_UPPER:
            score += 1
            reasons.append(f"RSI in range ({latest['RSI']:.1f})")
        
        # ============================================
        # CONDITION 7: ADX confirms trend strength
        # ============================================
        if latest['ADX'] > ADX_THRESHOLD:
            score += 1
            reasons.append(f"ADX > {ADX_THRESHOLD}")
        
        # ============================================
        # CONDITION 8: Price not at upper Bollinger Band
        # ============================================
        if latest['close'] < latest['BB_UPPER']:
            score += 1
            reasons.append("Price < BB_Upper")
        
        # ============================================
        # DECISION
        # ============================================
        if score >= MIN_SIGNAL_SCORE:
            signal = "BUY"
        elif score <= 2:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # Store for logging
        self.last_signal = signal
        self.signal_history.append({
            'time': df.index[-1],
            'signal': signal,
            'score': score,
            'price': latest['close'],
            'reasons': reasons
        })
        
        # Keep only last 100 signals
        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]
        
        return signal, score
    
    def get_signal_summary(self):
        """Get last signal details for display"""
        if not self.signal_history:
            return None
        return self.signal_history[-1]

# ============================================
# SESSION FILTER
# ============================================
class SessionFilter:
    """Determines if current time is suitable for trading"""
    
    @staticmethod
    def is_trading_allowed():
        """Check if trading is allowed at current time"""
        now = datetime.now()
        current_time = now.time()
        weekday = now.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        
        # Weekend - no trading
        if weekday >= 5:
            return False, "Weekend"
        
        # Friday afternoon
        if weekday == 4 and current_time >= time(16, 0) and not TRADE_FRIDAY_AFTERNOON:
            return False, "Friday afternoon"
        
        # London Open (07:00-09:00 GMT)
        london_open = time(7, 0) <= current_time <= time(9, 0)
        # London-NY Overlap (12:00-16:00 GMT)
        london_ny = time(12, 0) <= current_time <= time(16, 0)
        # Asian session (00:00-07:00 GMT)
        asian = time(0, 0) <= current_time <= time(7, 0)
        
        if london_open and TRADE_LONDON_OPEN:
            return True, "London Open"
        elif london_ny and TRADE_LONDON_NY_OVERLAP:
            return True, "London-NY Overlap"
        elif asian and TRADE_ASIAN:
            return True, "Asian Session"
        elif not asian and not london_open and not london_ny:
            return True, "Other Session"
        else:
            return False, "Outside trading hours"

# ============================================
# RISK MANAGER
# ============================================
class RiskManager:
    """Controls position sizing and risk limits"""
    
    def __init__(self, connection):
        self.connection = connection
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.daily_pnl = 0
        self.starting_balance = connection.get_balance()
        self.is_paused = False
        self.pause_until = None
        self.max_drawdown = 0
        self.peak_balance = self.starting_balance
    
    def can_trade(self):
        """Check if trading is currently allowed"""
        # Check if paused
        if self.is_paused:
            if datetime.now() > self.pause_until:
                self.is_paused = False
                self.consecutive_losses = 0
                logger.log("🟢 Cooldown period ended. Resuming trading.")
            else:
                remaining = (self.pause_until - datetime.now()).seconds // 60
                logger.log(f"⏸️  Paused. {remaining} minutes remaining.")
                return False
        
        # Check daily loss limit
        current_balance = self.connection.get_balance()
        self.daily_pnl = current_balance - self.starting_balance
        
        if self.daily_pnl < -(self.starting_balance * MAX_DAILY_LOSS_PCT):
            logger.log(f"🔴 Daily loss limit reached (${abs(self.daily_pnl):.2f}). Stopping for the day.", "WARNING")
            return False
        
        # Check if balance is too low
        if current_balance < 10:
            logger.log("🔴 Balance too low. Stopping.", "WARNING")
            return False
        
        return True
    
    def calculate_position_size(self, symbol=SYMBOL):
        """Calculate lot size based on risk parameters"""
        balance = self.connection.get_balance()
        risk_amount = balance * RISK_PER_TRADE
        
        # Get symbol info
        info = mt5.symbol_info(symbol)
        if info is None:
            return 0.01
        
        # Calculate pip value
        # For most forex pairs, 1 pip = 10 units of quote currency for 1 standard lot
        point_value = info.trade_tick_value  # Value of one tick
        tick_size = info.trade_tick_size     # Size of one tick
        
        # For EURUSD: tick_size usually 0.00001, point usually 0.00001
        # 1 pip = 0.0001 = 10 points
        pips_to_points = 10 if info.digits == 5 else 1
        
        # Value per pip for 1 lot
        pip_value = point_value * (pips_to_points * tick_size / info.point) if info.point else 10
        
        if pip_value <= 0:
            pip_value = 10  # Default for major pairs
        
        # Lot size = Risk Amount / (Stop Loss in pips * Pip Value)
        lot_size = risk_amount / (STOP_LOSS_PIPS * pip_value)
        
        # Round to 2 decimal places (standard for forex)
        lot_size = round(lot_size, 2)
        
        # Apply limits
        min_lot = info.volume_min
        max_lot = info.volume_max
        
        lot_size = max(min_lot, min(lot_size, max_lot))
        
        return lot_size
    
    def update_after_trade(self, profit):
        """Update statistics after a trade closes"""
        self.total_trades += 1
        
        if profit > 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.winning_trades += 1
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        self.daily_pnl += profit
        
        # Update drawdown tracking
        current_balance = self.connection.get_balance()
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        drawdown = (self.peak_balance - current_balance) / self.peak_balance * 100 if self.peak_balance > 0 else 0
        self.max_drawdown = max(self.max_drawdown, drawdown)
        
        # Circuit breaker
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            logger.log(f"🔴 {MAX_CONSECUTIVE_LOSSES} consecutive losses! Circuit breaker activated.", "WARNING")
            logger.log(f"   Pausing for {COOLDOWN_MINUTES} minutes...")
            self.is_paused = True
            self.pause_until = datetime.now() + pd.Timedelta(minutes=COOLDOWN_MINUTES)
    
    def get_stats(self):
        """Return current statistics"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'daily_pnl': self.daily_pnl,
            'max_drawdown': self.max_drawdown,
            'balance': self.connection.get_balance(),
            'equity': self.connection.get_equity(),
        }

# ============================================
# EXECUTION ENGINE
# ============================================
class ExecutionEngine:
    """Places and manages trades on MT5"""
    
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.open_positions = []
    
    def place_trade(self, signal, symbol=SYMBOL):
        """Execute a trade based on signal"""
        if signal not in ['BUY', 'SELL']:
            return None
        
        # Check spread
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if tick and info:
            spread = (tick.ask - tick.bid) / info.point
            if spread > MAX_SPREAD_PIPS:
                logger.log(f"⚠️ Spread too high ({spread:.1f} pips). Skipping trade.")
                return None
        
        # Calculate position size
        lot_size = self.risk_manager.calculate_position_size(symbol)
        
        # Prepare order
        if signal == 'BUY':
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
            sl = price - (STOP_LOSS_PIPS * 0.0001)  # Convert pips to price
            tp = price + (TAKE_PROFIT_PIPS * 0.0001)
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
            sl = price + (STOP_LOSS_PIPS * 0.0001)
            tp = price - (TAKE_PROFIT_PIPS * 0.0001)
        
        # Build trade request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 10,
            "magic": 123456,
            "comment": "AI_Forex_Bot_v2",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        logger.log(f"📤 Sending {signal} order: {lot_size} lots @ {price}")
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.log(f"✅ Trade executed successfully!")
            logger.log(f"   Ticket: {result.order}")
            logger.log(f"   Volume: {result.volume}")
            logger.log(f"   Price: {result.price}")
            logger.log(f"   SL: {sl} | TP: {tp}")
            return result
        else:
            logger.log(f"❌ Trade failed: {result.comment}", "ERROR")
            logger.log(f"   Retcode: {result.retcode}")
            return None
    
    def check_open_positions(self, symbol=SYMBOL):
        """Check status of open positions"""
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []
        return list(positions)

# ============================================
# MAIN BOT CONTROLLER
# ============================================
class ForexAIBot:
    """Main bot controller - orchestrates all components"""
    
    def __init__(self):
        self.connection = MT5Connection()
        self.market_data = None
        self.analysis = TechnicalAnalysis()
        self.signal_engine = SignalEngine()
        self.session_filter = SessionFilter()
        self.risk_manager = None
        self.execution = None
        self.running = False
    
    def initialize(self):
        """Initialize all components"""
        logger.log("=" * 60)
        logger.log("   AUTONOMOUS FOREX AI TRADING BOT v2.0")
        logger.log("=" * 60)
        
        # Connect to MT5
        if not self.connection.connect():
            return False
        
        # Initialize components
        self.market_data = MarketData(self.connection)
        self.risk_manager = RiskManager(self.connection)
        self.execution = ExecutionEngine(self.risk_manager)
        
        logger.log("✅ All systems initialized")
        logger.log(f"📊 Symbol: {SYMBOL}")
        logger.log(f"⏱️  Timeframe: {TIMEFRAME}")
        logger.log(f"💰 Risk per trade: {RISK_PER_TRADE*100}%")
        logger.log(f"🛑 Max daily loss: {MAX_DAILY_LOSS_PCT*100}%")
        logger.log(f"⏸️  Circuit breaker: {MAX_CONSECUTIVE_LOSSES} losses → {COOLDOWN_MINUTES}min pause")
        logger.log(f"🎯 SL: {STOP_LOSS_PIPS} pips | TP: {TAKE_PROFIT_PIPS} pips")
        logger.log("-" * 60)
        
        return True
    
    def run_once(self):
        """Execute one iteration of the trading loop"""
        try:
            # 1. Check session filter
            allowed, session_reason = self.session_filter.is_trading_allowed()
            if not allowed:
                logger.log(f"⏸️  Session: {session_reason} - Skipping analysis")
                return
            
            # 2. Check risk manager
            if not self.risk_manager.can_trade():
                return
            
            # 3. Check if market is open
            if not self.market_data.is_market_open():
                logger.log("⚠️ Market closed. Waiting...")
                return
            
            # 4. Check spread
            spread = self.market_data.get_spread()
            if spread > MAX_SPREAD_PIPS * 10:  # Convert pips to points
                logger.log(f"⚠️ Spread too high ({spread} points). Skipping.")
                return
            
            # 5. Get market data
            df = self.market_data.get_candles()
            if df is None:
                return
            
            # 6. Add indicators
            df = self.analysis.add_all_indicators(df)
            
            # 7. Generate signal
            signal, score = self.signal_engine.analyze(df)
            
            # 8. Get latest values for display
            latest = df.iloc[-1]
            bid, ask = self.market_data.get_current_price()
            
            # 9. Display analysis
            logger.log(f"\n{'─'*50}")
            logger.log(f"🕐 {datetime.now().strftime('%H:%M:%S')} | {SYMBOL} | {TIMEFRAME}")
            logger.log(f"💵 Bid: {bid:.5f} | Ask: {ask:.5f} | Spread: {self.market_data.get_spread()} pts")
            logger.log(f"📊 Price: {latest['close']:.5f}")
            logger.log(f"   SMA({SMA_FAST}): {latest['SMA_FAST']:.5f} | SMA({SMA_SLOW}): {latest['SMA_SLOW']:.5f}")
            logger.log(f"   MACD: {latest['MACD']:.5f} | Signal: {latest['MACD_SIGNAL']:.5f}")
            logger.log(f"   RSI: {latest['RSI']:.1f} | ADX: {latest['ADX']:.1f}")
            logger.log(f"   BB Width: {latest['BB_WIDTH_PCT']:.2f}%")
            logger.log(f"🎯 Signal: {signal} | Score: {score}/8 | Session: {session_reason}")
            
            # 10. Execute trade if signal
            if signal in ['BUY', 'SELL']:
                result = self.execution.place_trade(signal)
                
                if result:
                    # Monitor this position
                    logger.log("👀 Monitoring position...")
                    time_module.sleep(3)
                    
                    # Check if position still open (not instantly closed by SL/TP)
                    positions = self.execution.check_open_positions()
                    if len(positions) == 0:
                        # Position already closed - check P&L
                        history = mt5.history_deals_get(
                            position=result.order,
                            ticket=result.order
                        )
                        if history and len(history) > 0:
                            profit = sum(deal.profit for deal in history)
                            self.risk_manager.update_after_trade(profit)
                            logger.log(f"💰 Position closed. P&L: ${profit:.2f}")
            
            # 11. Display stats
            stats = self.risk_manager.get_stats()
            logger.log(f"📈 Stats: {stats['total_trades']} trades | "
                      f"Win Rate: {stats['win_rate']:.1f}% | "
                      f"Daily P&L: ${stats['daily_pnl']:.2f} | "
                      f"Balance: ${stats['balance']:.2f}")
            
        except Exception as e:
            logger.log(f"❌ Error in run_once: {str(e)}", "ERROR")
    
    def run(self):
        """Main bot loop"""
        if not self.initialize():
            logger.log("❌ Failed to initialize. Exiting.", "ERROR")
            return
        
        self.running = True
        logger.log("🚀 Bot started! Running autonomous trading...")
        logger.log("   Press Ctrl+C to stop")
        
        try:
            while self.running:
                self.run_once()
                logger.log(f"⏳ Next analysis in 60 seconds...")
                time_module.sleep(60)
                
        except KeyboardInterrupt:
            logger.log("\n🛑 Bot stopped by user.")
        except Exception as e:
            logger.log(f"❌ Fatal error: {e}", "ERROR")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        self.running = False
        self.connection.disconnect()
        logger.log("👋 Bot shutdown complete.")
        
        # Final stats
        if self.risk_manager:
            stats = self.risk_manager.get_stats()
            logger.log(f"\n{'='*40}")
            logger.log(f"FINAL STATISTICS:")
            logger.log(f"   Total Trades: {stats['total_trades']}")
            logger.log(f"   Win Rate: {stats['win_rate']:.1f}%")
            logger.log(f"   Daily P&L: ${stats['daily_pnl']:.2f}")
            logger.log(f"   Max Drawdown: {stats['max_drawdown']:.1f}%")
            logger.log(f"   Final Balance: ${stats['balance']:.2f}")
            logger.log(f"{'='*40}")

# ============================================
# ENTRY POINT
# ============================================
if __name__ == "__main__":
    bot = ForexAIBot()
    bot.run()
