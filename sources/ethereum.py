import requests
import streamlit as st

from config import REFRESH_INTERVAL

BLOCKSCOUT_API = "https://eth.blockscout.com/api"
# Lido stETH is a rebasing ERC-20: balanceOf grows with staking rewards, so the
# token balance alone reflects accrued rewards. 18 decimals, like ETH.
STETH_CONTRACT = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"


def _query(params):
    resp = requests.get(BLOCKSCOUT_API, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "1":
        raise ValueError(data.get("message", "unknown Blockscout error"))
    return int(data["result"]) / 1e18


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_balances(address):
    """(eth_balance, steth_balance) for the address; each None on failure or if unset."""
    if not address:
        return None, None
    eth = steth = None
    try:
        eth = _query({"module": "account", "action": "balance", "address": address})
    except Exception as e:
        st.warning(f"Could not fetch ETH balance: {e}")
    try:
        steth = _query({
            "module": "account",
            "action": "tokenbalance",
            "contractaddress": STETH_CONTRACT,
            "address": address,
        })
    except Exception as e:
        st.warning(f"Could not fetch stETH balance: {e}")
    return eth, steth
