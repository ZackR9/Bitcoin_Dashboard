import requests
import streamlit as st
import yfinance as yf

from config import REFRESH_INTERVAL

COINGECKO_PRICE_API = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_COIN_API = "https://api.coingecko.com/api/v3/coins/{id}"
GOLD_API = "https://api.gold-api.com/price/{symbol}"
# frankfurter.app 301s to a Cloudflare page; only the .dev domain serves JSON.
FRANKFURTER_API = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=CAD"

CORE_COINS = ("bitcoin", "ethereum", "staked-ether")
# Futures contracts used only for day-change reference points (open/prev close);
# gold-api.com stays the spot-price source.
METAL_FUTURES = {"XAU": "GC=F", "XAG": "SI=F"}


def _fast_info_value(info, key):
    try:
        value = info[key]
        return None if value is None else float(value)
    except Exception:
        return None


# --- Crypto (CoinGecko) ---
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_crypto_prices(ids=CORE_COINS):
    """{coin_id: {'cad': .., 'usd': .., 'cad_24h_change': ..}} or None.

    ids must be a tuple (hashable for the cache)."""
    try:
        resp = requests.get(
            COINGECKO_PRICE_API,
            params={
                "ids": ",".join(ids),
                "vs_currencies": "cad,usd",
                "include_24hr_change": "true",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Could not fetch crypto prices: {e}")
        return None


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_coin_info(coin_id):
    """Subset of CoinGecko coin metadata for the investment detail view; {} on failure."""
    try:
        resp = requests.get(
            COINGECKO_COIN_API.format(id=coin_id),
            params={
                "localization": "false", "tickers": "false",
                "community_data": "false", "developer_data": "false",
                "sparkline": "false",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        md = data.get("market_data") or {}
        return {
            "name": data.get("name"),
            "symbol": (data.get("symbol") or "").upper(),
            "rank": data.get("market_cap_rank"),
            "description": (data.get("description") or {}).get("en", ""),
            "market_cap_cad": (md.get("market_cap") or {}).get("cad"),
            "ath_cad": (md.get("ath") or {}).get("cad"),
            "change_7d_pct": md.get("price_change_percentage_7d"),
            "change_30d_pct": md.get("price_change_percentage_30d"),
        }
    except Exception as e:
        st.warning(f"Could not fetch coin info for {coin_id}: {e}")
        return {}


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


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_metal_futures_refs(symbol):
    """last/open/previous_close (USD) of the metal's futures contract, used only
    to compute day/overnight percent changes; {} on failure."""
    future = METAL_FUTURES.get(symbol)
    if not future:
        return {}
    try:
        info = yf.Ticker(future).fast_info
        return {
            "last": _fast_info_value(info, "last_price"),
            "open": _fast_info_value(info, "open"),
            "previous_close": _fast_info_value(info, "previous_close"),
        }
    except Exception as e:
        st.warning(f"Could not fetch {future} for {symbol} day change: {e}")
        return {}


# --- Stocks/ETFs (Yahoo Finance) ---
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_stock_quotes(symbols):
    """symbols: tuple of Yahoo symbols. Returns
    {symbol: {'price', 'currency', 'open', 'previous_close'}} in the listing
    currency; symbols that fail to resolve are omitted (warned individually)."""
    quotes = {}
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).fast_info
            quotes[symbol] = {
                "price": info["last_price"],
                "currency": info["currency"],
                "open": _fast_info_value(info, "open"),
                "previous_close": _fast_info_value(info, "previous_close"),
            }
        except Exception as e:
            st.warning(f"Could not fetch quote for {symbol}: {e}")
    return quotes


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_stock_info(symbol):
    """Subset of Yahoo's .info for the investment detail view; {} on failure."""
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as e:
        st.warning(f"Could not fetch info for {symbol}: {e}")
        return {}
    keys = [
        "longName", "shortName", "quoteType", "sector", "industry", "currency",
        "marketCap", "trailingPE", "dividendYield", "fiftyTwoWeekLow",
        "fiftyTwoWeekHigh", "category", "fundFamily", "longBusinessSummary",
    ]
    return {k: info.get(k) for k in keys if info.get(k) is not None}
