import requests
import streamlit as st
import yfinance as yf

from config import REFRESH_INTERVAL

COINGECKO_API = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,staked-ether&vs_currencies=cad,usd"
)
GOLD_API = "https://api.gold-api.com/price/{symbol}"
# frankfurter.app 301s to a Cloudflare page; only the .dev domain serves JSON.
FRANKFURTER_API = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=CAD"


# --- Crypto (CoinGecko) ---
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_crypto_prices():
    """{'bitcoin': {'cad': .., 'usd': ..}, 'ethereum': {...}, 'staked-ether': {...}} or None."""
    try:
        resp = requests.get(COINGECKO_API, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Could not fetch crypto prices: {e}")
        return None


# --- FX (Frankfurter, ECB rates) ---
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_usd_cad():
    try:
        resp = requests.get(FRANKFURTER_API, timeout=10)
        resp.raise_for_status()
        return resp.json()["rates"]["CAD"]
    except Exception as e:
        st.warning(f"Could not fetch USD/CAD rate: {e}")
        return None


# --- Metals spot (gold-api.com, USD/oz) ---
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_metal_spot_usd(symbol):
    """symbol: 'XAU' (gold) or 'XAG' (silver). USD per troy ounce, or None."""
    try:
        resp = requests.get(GOLD_API.format(symbol=symbol), timeout=10)
        resp.raise_for_status()
        return resp.json()["price"]
    except Exception as e:
        st.warning(f"Could not fetch {symbol} spot price: {e}")
        return None


# --- Stocks/ETFs (Yahoo Finance) ---
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_stock_quotes(symbols):
    """symbols: tuple of Yahoo symbols. Returns {symbol: {'price': .., 'currency': ..}};
    symbols that fail to resolve are omitted (warned individually)."""
    quotes = {}
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).fast_info
            quotes[symbol] = {"price": info["last_price"], "currency": info["currency"]}
        except Exception as e:
            st.warning(f"Could not fetch quote for {symbol}: {e}")
    return quotes
