import os

import pandas as pd
import streamlit as st


def get_cost_basis(csv_path, asset):
    """Cost basis for one asset ('BTC' or 'ETH') from Shakepay buys.

    Returns dict with amount_purchased, cad_spent, avg_price, buys (DataFrame),
    or None if the CSV is unavailable."""
    if not csv_path or not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
        df["Date"] = pd.to_datetime(df["Date"])
    except Exception as e:
        st.error(f"Could not read Shakepay CSV: {e}")
        return None
    buys = df[(df["Type"] == "Buy") & (df["Asset Credited"] == asset)].copy()
    amount = buys["Amount Credited"].sum()
    spent = buys["Book Cost"].sum()
    return {
        "amount_purchased": amount,
        "cad_spent": spent,
        "avg_price": spent / amount if amount > 0 else 0,
        "buys": buys,
    }
