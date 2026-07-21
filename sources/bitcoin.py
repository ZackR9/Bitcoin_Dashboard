import requests
import streamlit as st

from config import REFRESH_INTERVAL

BLOCKSTREAM_API = "https://blockstream.info/api/address/{address}"


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_balance(addresses):
    """Sum of confirmed balances (BTC) across addresses; None if no addresses configured."""
    if not addresses:
        return None
    total_sats = 0
    for address in addresses:
        try:
            resp = requests.get(BLOCKSTREAM_API.format(address=address), timeout=10)
            resp.raise_for_status()
            stats = resp.json().get("chain_stats", {})
            total_sats += stats.get("funded_txo_sum", 0) - stats.get("spent_txo_sum", 0)
        except Exception as e:
            st.warning(f"Could not fetch BTC balance for {address}: {e}")
    return total_sats / 1e8
