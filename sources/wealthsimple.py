import os
import shutil

import pandas as pd
import streamlit as st

HOLDINGS_COLUMNS = ["account", "symbol", "shares", "book_cost_cad"]

# Wealthsimple export column names drift between account types and app versions,
# so each field is matched against several candidates (compared lowercased).
EXPORT_COLUMN_CANDIDATES = {
    "symbol": ["symbol", "ticker"],
    "quantity": ["quantity", "shares", "qty"],
    "type": ["transaction", "transaction type", "type", "activity", "activity type"],
    "amount": ["amount", "net amount", "total amount", "book value", "book cost", "market value"],
    "date": ["date", "trade date", "process date", "transaction date"],
    "account": ["account", "account type", "account number"],
}


# --- Holdings CSV (source of truth, user-maintained) ---
def load_holdings(csv_path):
    if not csv_path or not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
        missing = [c for c in HOLDINGS_COLUMNS if c not in df.columns]
        if missing:
            st.error(f"Holdings CSV is missing columns: {missing}")
            return None
        return df
    except Exception as e:
        st.error(f"Could not read holdings CSV: {e}")
        return None


def save_holdings(df, csv_path):
    if os.path.exists(csv_path):
        shutil.copy2(csv_path, csv_path + ".bak")
    df.to_csv(csv_path, index=False)


# --- Wealthsimple export parsing ---
def _match_columns(df):
    lower = {c.lower().strip(): c for c in df.columns}
    matched = {}
    for field, candidates in EXPORT_COLUMN_CANDIDATES.items():
        for cand in candidates:
            if cand in lower:
                matched[field] = lower[cand]
                break
    return matched


def parse_export(uploaded_file):
    """Parse a Wealthsimple activity export into holdings rows.

    Returns (holdings_df, error). Buys accumulate shares and book cost; sells
    reduce book cost at the running average (ACB), matching how the holdings
    CSV is meant to be maintained."""
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        return None, f"Could not read the uploaded file as CSV: {e}"

    cols = _match_columns(df)
    required = ["symbol", "quantity", "type", "amount"]
    missing = [f for f in required if f not in cols]
    if missing:
        return None, (
            f"Could not identify columns for: {missing}. "
            f"Columns found in file: {list(df.columns)}"
        )

    if "date" in cols:
        df[cols["date"]] = pd.to_datetime(df[cols["date"]], errors="coerce")
        df = df.sort_values(cols["date"])

    positions = {}
    for _, row in df.iterrows():
        tx_type = str(row[cols["type"]]).lower()
        is_buy = "buy" in tx_type
        is_sell = "sell" in tx_type
        if not (is_buy or is_sell):
            continue
        symbol = str(row[cols["symbol"]]).strip()
        if not symbol or symbol.lower() == "nan":
            continue
        account = str(row[cols["account"]]).strip() if "account" in cols else "UNKNOWN"
        qty = abs(pd.to_numeric(row[cols["quantity"]], errors="coerce"))
        amount = abs(pd.to_numeric(row[cols["amount"]], errors="coerce"))
        if pd.isna(qty) or qty == 0:
            continue
        pos = positions.setdefault((account, symbol), {"shares": 0.0, "book_cost_cad": 0.0})
        if is_buy:
            pos["shares"] += qty
            pos["book_cost_cad"] += 0 if pd.isna(amount) else amount
        elif pos["shares"] > 0:
            sold = min(qty, pos["shares"])
            pos["book_cost_cad"] -= pos["book_cost_cad"] / pos["shares"] * sold
            pos["shares"] -= sold

    rows = [
        {"account": account, "symbol": symbol, "shares": p["shares"],
         "book_cost_cad": round(p["book_cost_cad"], 2)}
        for (account, symbol), p in positions.items()
        if p["shares"] > 1e-9
    ]
    if not rows:
        return None, "No buy/sell rows with a symbol were found in the file."
    return pd.DataFrame(rows, columns=HOLDINGS_COLUMNS), None
