import os
import shutil

import pandas as pd
import streamlit as st

PURCHASE_COLUMNS = ["date", "metal", "ounces", "total_cost_cad", "source"]


def load_purchases(csv_path):
    """Purchases DataFrame (date, metal, ounces, total_cost_cad, source) or None."""
    if not csv_path or not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
        missing = [c for c in PURCHASE_COLUMNS[:4] if c not in df.columns]
        if missing:
            st.error(f"Metals CSV is missing columns: {missing}")
            return None
        df["date"] = pd.to_datetime(df["date"])
        df["metal"] = df["metal"].str.lower().str.strip()
        return df
    except Exception as e:
        st.error(f"Could not read metals CSV: {e}")
        return None


def save_purchases(df, csv_path):
    if os.path.exists(csv_path):
        shutil.copy2(csv_path, csv_path + ".bak")
    df.to_csv(csv_path, index=False)


def summarize(purchases):
    """{metal: {'ounces': .., 'cost_cad': .., 'avg_cost_per_oz': ..}} per metal held."""
    summary = {}
    for metal, group in purchases.groupby("metal"):
        ounces = group["ounces"].sum()
        cost = group["total_cost_cad"].sum()
        summary[metal] = {
            "ounces": ounces,
            "cost_cad": cost,
            "avg_cost_per_oz": cost / ounces if ounces > 0 else 0,
        }
    return summary
