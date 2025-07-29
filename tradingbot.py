#Webull trading bot by Jackson Laughlin

from webull import webull
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from ta.momentum import RSIIndicator
from dotenv import load_dotenv
import os
import time

# Load credentials
load_dotenv()
EMAIL = os.getenv("WEBULL_EMAIL")
PASSWORD = os.getenv("WEBULL_PASSWORD")
PIN = os.getenv("WEBULL_PIN")
APIKEY = os.getenv("API_KEY")
APISECRET = os.getenv("API_SECRET")

def login_with_api_key (API_KEY, API_SECRET):
    print (f"Logging inusing API KEY: {API_KEY[:4]}****")

    return True

# Setup Webull client
wb = webull()
wb.login(EMAIL, PASSWORD)
wb.get_mfa(EMAIL)
wb.login(EMAIL, PASSWORD, device_name='ai_trader_bot')
wb.get_trade_token(PIN)
login_with_api_key(APIKEY, APISECRET)

# === CONFIG ===
QUANTITY = 1
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'META', 'GOOGL', 'AMD', 'NFLX', 'BA']  # example watchlist
INTERVAL = 'd'
BARS = 100

def fetch_data(symbol):
    try:
        bars = wb.get_bars(stock=symbol, interval=INTERVAL, count=BARS)
        df = pd.DataFrame(bars)
        df['close'] = df['close'].astype(float)
        df['rsi'] = RSIIndicator(df['close']).rsi()
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        return df.dropna()
    except Exception as e:
        print(f"Failed to get data for {symbol}: {e}")
        return None

def train_model(df):
    X = df[['rsi']]
    y = df['target']
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    return model

def get_buying_power():
    try:
        account = wb.get_account()
        return float(account.get('accountMembers', [{}])[0].get('account', {}).get('cashBuyingPower', 0))
    except Exception as e:
        print("Error fetching buying power:", e)
        return 0
def get_dynamic_tickers(limit=10):
    try:
        gainers = wb.get_top_gainers()
        tickers = [item['ticker'] for item in gainers[:limit]]
        print(f"Dynamically selected tickers: {tickers}")
        return tickers
    except Exception as e:
        print("Error fetching dynamic tickers:", e)
        return ['AAPL']  # fallback
def select_best_trade(tickers):
    tickers = get_dynamic_tickers(limt=100)
    candidates = []

    for symbol in tickers:
        df = fetch_data(symbol)
        if df is None or len(df) < 10:
            continue
        model = train_model(df)
        latest_rsi = RSIIndicator(df['close']).rsi().iloc[-1]
        pred = model.predict([[latest_rsi]])[0]
        prob = model.predict_proba([[latest_rsi]])[0][1]  # probability of "up"
        if pred == 1:
            if df['close'].iloc[-1] <= get_buying_power():  # Only consider affordable stocks
              candidates.append((symbol, prob, df['close'].iloc[-1]))

    
    if not candidates:
        print("No strong buy candidates found today.")
        return None
    
    # Sort by model confidence (probability of upward move)
    best = sorted(candidates, key=lambda x: x[1], reverse=True)[0]
    return best

def place_trade(symbol, price):
    buying_power = get_buying_power()
    if buying_power >= price * QUANTITY:
        print(f"Placing BUY order for {symbol}...")
        try:
            wb.place_order(
                stock=wb.get_stock(symbol),
                action='BUY',
                orderType='MKT',
                enforce='GTC',
                quant=QUANTITY,
                price=0  # ignored for market order
            )
        except Exception as e:
            print(f"Failed to place order for {symbol}: {e}")
    else:
        print(f"Not enough buying power (${buying_power:.2f}) to buy {symbol} at ${price:.2f}")

# === RUN BOT ===
best_trade = select_best_trade(TICKERS)
if best_trade:
    symbol, confidence, price = best_trade
    print(f"Top pick: {symbol} (Confidence: {confidence:.2f}) at ${price:.2f}")
    place_trade(symbol, price)



