# Autonomous AI Forex Trading Bot

An intelligent, fully-automated forex trading bot that connects to Exness via MetaTrader 5. Uses multi-indicator analysis with risk management to trade EUR/USD autonomously.

## Features

- **8-Condition AI Signal Engine** - SMA, EMA, MACD, RSI, ADX, Bollinger Bands
- **Smart Risk Management** - 2% risk per trade, stop loss, take profit
- **Circuit Breaker** - Auto-pauses after consecutive losses
- **Session Filter** - Trades only during high-liquidity sessions
- **Position Sizing** - Auto-calculates lot size based on account balance
- **Comprehensive Logging** - All trades and decisions logged

## Requirements

- Python 3.8+
- MetaTrader 5 terminal (with Exness account)
- Windows PC (MT5 requirement)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/YOUR_USERNAME/forex-ai-bot.git
cd forex-ai-bot 
