"""Cached price-history fetchers for the investment detail charts.

All return a DataFrame with columns ts (datetime) and price, or None on
failure. Stocks/futures come from yfinance in the listing currency; crypto
from CoinGecko in CAD.
"""

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from config import REFRESH_INTERVAL

COINGECKO_CHART_API = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"

# period key -> (yfinance period/interval, CoinGecko days)
PERIODS = {
    "1D": {"yf": ("1d", "5m"), "days": "1"},
    "1W": {"yf": ("5d", "30m"), "days": "7"},
    "1M": {"yf": ("1mo", "1d"), "days": "30"},
    "1Y": {"yf": ("1y", "1d"), "days": "365"},
    "Max": {"yf": ("max", "1wk"), "days": "max"},
}


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_stock_history(symbol, period_key):
    try:
        period, interval = PERIODS[period_key]["yf"]
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        return pd.DataFrame({"ts": df[df.columns[0]], "price": df["Close"]})
    except Exception as e:
        st.warning(f"Could not fetch history for {symbol}: {e}")
        return None


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_crypto_history(coin_id, period_key):
    try:
        resp = requests.get(
            COINGECKO_CHART_API.format(id=coin_id),
            params={"vs_currency": "cad", "days": PERIODS[period_key]["days"]},
            timeout=15,
        )
        resp.raise_for_status()
        points = resp.json().get("prices", [])
        if not points:
            return None
        return pd.DataFrame({
            "ts": pd.to_datetime([p[0] for p in points], unit="ms"),
            "price": [p[1] for p in points],
        })
    except Exception as e:
        st.warning(f"Could not fetch history for {coin_id}: {e}")
        return None
