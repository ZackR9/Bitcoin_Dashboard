"""Persistence for user-entered state, all under DATA_DIR.

Two files:
- state.json        cash balance, watchlist, crypto adjustments
- transactions.csv  the buy ledger (tax record of date/price/quantity)

Every write backs up the previous file as .bak and goes through a temp file so
a crash mid-write can't corrupt the data.
"""

import json
import os
import shutil

import pandas as pd
import streamlit as st

from config import DATA_DIR

STATE_PATH = os.path.join(DATA_DIR, "state.json")
TRANSACTIONS_PATH = os.path.join(DATA_DIR, "transactions.csv")
TRANSACTION_COLUMNS = [
    "date", "asset_class", "symbol", "quantity", "price_cad", "total_cad", "account", "note",
]
DEFAULT_STATE = {
    # None -> fall back to config.json cash.chequing_cad (legacy location).
    "cash_cad": None,
    # [{"symbol": "VFV.TO", "kind": "stock"}, {"symbol": "solana", "kind": "crypto"}]
    # For kind "crypto" the symbol is a CoinGecko id.
    "watchlist": [],
    # {coin_id: {"quantity": float, "cost_cad": float}} — added on top of
    # on-chain balances / Shakepay basis for coins those sources don't cover.
    "crypto_adjustments": {},
}


def _backup(path):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")


def _write_atomic(path, write_fn):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    _backup(path)
    tmp = path + ".tmp"
    write_fn(tmp)
    os.replace(tmp, path)


# --- state.json ---
def load_state():
    state = dict(DEFAULT_STATE)
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r") as f:
                state.update(json.load(f))
        except Exception as e:
            st.warning(f"Could not read {STATE_PATH}: {e}")
    return state


def save_state(state):
    def write(tmp):
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)

    _write_atomic(STATE_PATH, write)


# --- transactions.csv (buy ledger) ---
def load_transactions():
    if not os.path.exists(TRANSACTIONS_PATH):
        return pd.DataFrame(columns=TRANSACTION_COLUMNS)
    try:
        return pd.read_csv(TRANSACTIONS_PATH)
    except Exception as e:
        st.error(f"Could not read transactions ledger: {e}")
        return pd.DataFrame(columns=TRANSACTION_COLUMNS)


def save_transactions(df):
    _write_atomic(TRANSACTIONS_PATH, lambda tmp: df.to_csv(tmp, index=False))


def append_transaction(row):
    df = load_transactions()
    df = pd.concat([df, pd.DataFrame([row], columns=TRANSACTION_COLUMNS)], ignore_index=True)
    save_transactions(df)


# --- uploaded files (e.g. Shakepay export) ---
def save_uploaded(path, uploaded_file):
    _write_atomic(path, lambda tmp: open(tmp, "wb").write(uploaded_file.getbuffer()))
