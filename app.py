import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import os

# --- Load config file ---
CONFIG_PATH = "config.json"
config = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
else:
    st.warning(f"Config file '{CONFIG_PATH}' not found. Please create it to enable dynamic data loading.")

# --- Get settings from config or fallback ---
COINGECKO_API = config.get("api_settings", {}).get(
    "coingecko_api",
    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=cad,usd"
)
SHAKEPAY_CSV_PATH = config.get("data_sources", {}).get("shakepay_csv_path", None)
LEDGER_ADDRESS = config.get("data_sources", {}).get("ledger_address", "")
REFRESH_INTERVAL = config.get("api_settings", {}).get("refresh_interval", 300)

st.set_page_config(page_title="BTC Tax Tracker", page_icon="🪙")
st.title("🪙 Bitcoin Tax & Profit Tracker")

# --- Get current BTC price ---
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_btc_price():
    response = requests.get(COINGECKO_API)
    return response.json()['bitcoin']

current_prices = get_btc_price()
current_price_cad = current_prices['cad']
current_price_usd = current_prices['usd']

# --- Ledger balance input (auto-fetch from config) ---
def get_ledger_balance(address):
    url = f"https://blockstream.info/api/address/{address}"
    try:
        resp = requests.get(url)
        data = resp.json()
        sats = data.get("chain_stats", {}).get("funded_txo_sum", 0) - data.get("chain_stats", {}).get("spent_txo_sum", 0)
        btc = sats / 1e8
        return btc
    except Exception as e:
        st.warning(f"Could not fetch Ledger balance automatically: {e}")
        return None

ledger_btc_balance = get_ledger_balance(LEDGER_ADDRESS)
ledger_value_cad = ledger_btc_balance * current_price_cad if ledger_btc_balance is not None else 0
ledger_value_usd = ledger_btc_balance * current_price_usd if ledger_btc_balance is not None else 0

# --- Shakepay CSV auto-load from config ---
if SHAKEPAY_CSV_PATH and os.path.exists(SHAKEPAY_CSV_PATH):
    df = pd.read_csv(SHAKEPAY_CSV_PATH)
    df['Date'] = pd.to_datetime(df['Date'])
    btc_buys = df[(df['Type'] == 'Buy') & (df['Asset Credited'] == 'BTC')].copy()
    total_btc_purchased = btc_buys['Amount Credited'].sum()
    total_cad_spent = btc_buys['Book Cost'].sum()
    average_buy_price = total_cad_spent / total_btc_purchased if total_btc_purchased > 0 else 0
else:
    st.error("Shakepay CSV file not found or path not set in config.")
    btc_buys = pd.DataFrame()
    total_btc_purchased = 0
    total_cad_spent = 0
    average_buy_price = 0

# --- Display Main Dashboard ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("BTC Price (CAD)", f"${current_price_cad:,.2f}")
    st.metric("BTC Price (USD)", f"${current_price_usd:,.2f}")
with col2:
    st.metric("Total Ledger Balance (BTC)", f"{ledger_btc_balance:.8f}")
    st.metric("Total Ledger Balance (CAD)", f"${ledger_value_cad:,.2f}")
    st.metric("Total Ledger Balance (USD)", f"${ledger_value_usd:,.2f}")
with col3:
    st.metric("Average Buy Price (Shakepay, CAD)", f"${average_buy_price:,.2f}")

# --- P&L Calculation (Ledger minus Shakepay cost basis) ---
if ledger_btc_balance is not None and total_cad_spent > 0:
    pnl_cad = (ledger_btc_balance * current_price_cad) - total_cad_spent
    pnl_pct = (pnl_cad / total_cad_spent) * 100
    st.metric("Total P&L (CAD, Ledger minus Shakepay cost)", f"${pnl_cad:,.2f}", delta=f"{pnl_pct:.2f}%")
else:
    st.info("P&L cannot be calculated (missing Ledger balance or Shakepay cost basis).")

# --- Tax Information ---
st.subheader("📋 Tax Information (Canada)")
st.write(f"**Tax Year:** {datetime.now().year}")
st.write(f"**Cost Basis (ACB from Shakepay):** ${total_cad_spent:,.2f} CAD")
if ledger_btc_balance is not None:
    fair_market_value = ledger_btc_balance * current_price_cad
    unrealized_gain = fair_market_value - total_cad_spent
    if unrealized_gain > 0:
        st.write(f"**Unrealized Capital Gain (50% taxable):** ${unrealized_gain * 0.5:,.2f} CAD")
        st.info("💡 This is unrealized gain. Capital gains tax only applies when you sell or dispose of your Bitcoin.")
    else:
        st.write(f"**Unrealized Capital Loss:** ${abs(unrealized_gain):,.2f} CAD")
else:
    st.info("Ledger balance not available for tax calculation.")

st.warning("⚠️ If you purchased BTC from other exchanges before Shakepay, you'll need to add those transactions manually or consult a tax professional for accurate cost basis.")

# Footer
st.markdown("---")
st.caption("⚠️ This tool is for informational purposes only. Consult a tax professional for official tax advice.")

# Run: streamlit run app.py