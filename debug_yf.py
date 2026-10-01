import os
import yfinance as yf
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    print("Testing yfinance for TSLA...")
    stock = yf.Ticker("TSLA")
    hist = stock.history(period="5d")
    print(hist)
    print("Current Price:", stock.info.get('currentPrice'))
except Exception as e:
    print("Error:", e)
