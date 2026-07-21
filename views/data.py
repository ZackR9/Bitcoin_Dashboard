import os

import pandas as pd
import streamlit as st

import config
import store
from sources import metals as metals_source
from sources import shakepay, wealthsimple
from ui import cad

cfg = config.load()
state = store.load_state()

st.title("🗂️ Manage Data")
st.caption(
    f"All files live in the data directory (`{os.path.abspath(config.DATA_DIR)}`). "
    "Every save backs up the previous file as `.bak`."
)

# --- Cash ---
st.header("Cash")
current_cash = state["cash_cad"] if state["cash_cad"] is not None else cfg["cash_cad"]
cash = st.number_input(
    "Wealthsimple chequing balance (CAD)", min_value=0.0,
    value=float(current_cash), step=100.0,
)
if st.button("Save cash balance"):
    state["cash_cad"] = cash
    store.save_state(state)
    st.success("Cash balance saved.")

# --- Stocks/ETFs ---
st.header("Stocks / ETFs")
st.caption(
    "Source of truth for your Wealthsimple positions. Symbols in Yahoo format "
    "(e.g. VFV.TO). Edit cells, add or delete rows, then save."
)
holdings = wealthsimple.load_holdings(cfg["stocks_holdings_csv_path"])
if holdings is None:
    holdings = pd.DataFrame(columns=wealthsimple.HOLDINGS_COLUMNS)
edited_holdings = st.data_editor(
    holdings, num_rows="dynamic", use_container_width=True, key="holdings_editor",
)
if st.button("Save holdings"):
    wealthsimple.save_holdings(edited_holdings, cfg["stocks_holdings_csv_path"])
    st.success(f"Wrote {len(edited_holdings)} holdings to {cfg['stocks_holdings_csv_path']}.")

with st.expander("Rebuild holdings from a Wealthsimple activity export"):
    st.caption(
        "Upload an activity/transactions CSV exported from Wealthsimple. Buys and "
        "sells are aggregated into per-symbol positions (average-cost basis) and can "
        "replace the holdings CSV. Review the preview first — Wealthsimple symbols "
        "may need their Yahoo suffix added afterwards (e.g. VFV → VFV.TO)."
    )
    uploaded = st.file_uploader("Wealthsimple export CSV", type="csv", key="ws_upload")
    if uploaded is not None:
        proposed, error = wealthsimple.parse_export(uploaded)
        if error:
            st.error(error)
        else:
            st.write("**Proposed holdings:**")
            st.dataframe(proposed, use_container_width=True, hide_index=True)
            if st.button("Apply to holdings CSV"):
                wealthsimple.save_holdings(proposed, cfg["stocks_holdings_csv_path"])
                st.success(
                    f"Wrote {len(proposed)} holdings to {cfg['stocks_holdings_csv_path']} "
                    "(previous file backed up as .bak)."
                )

# --- Shakepay ---
st.header("Shakepay (crypto cost basis)")
for coin in ("BTC", "ETH"):
    basis = shakepay.get_cost_basis(cfg["shakepay_csv_path"], coin)
    if basis and basis["amount_purchased"] > 0:
        st.write(
            f"**{coin}:** {basis['amount_purchased']:.6f} bought for "
            f"{cad(basis['cad_spent'])} (avg {cad(basis['avg_price'])})"
        )
if not os.path.exists(cfg["shakepay_csv_path"] or ""):
    st.info("No Shakepay export on file yet — upload one below.")
sp_upload = st.file_uploader("Shakepay transactions export CSV", type="csv", key="sp_upload")
if sp_upload is not None and st.button("Save Shakepay export"):
    store.save_uploaded(cfg["shakepay_csv_path"], sp_upload)
    st.success(f"Saved to {cfg['shakepay_csv_path']} (previous file backed up as .bak).")
    st.rerun()

# --- Crypto adjustments ---
st.header("Crypto adjustments")
st.caption(
    "Quantity/cost added on top of the automatic numbers, for coins your tracked "
    "addresses and Shakepay export don't cover (still on Shakepay, bought elsewhere, "
    "or a coin the app doesn't track on-chain). `coin_id` is the CoinGecko id: "
    "bitcoin, ethereum, solana, …"
)
adj_df = pd.DataFrame(
    [
        {"coin_id": k, "quantity": v.get("quantity", 0.0), "cost_cad": v.get("cost_cad", 0.0)}
        for k, v in state["crypto_adjustments"].items()
    ],
    columns=["coin_id", "quantity", "cost_cad"],
)
edited_adj = st.data_editor(
    adj_df, num_rows="dynamic", use_container_width=True, key="adj_editor",
)
if st.button("Save adjustments"):
    state["crypto_adjustments"] = {
        str(r["coin_id"]).strip().lower(): {
            "quantity": float(r["quantity"] or 0),
            "cost_cad": float(r["cost_cad"] or 0),
        }
        for _, r in edited_adj.iterrows()
        if str(r["coin_id"]).strip() and str(r["coin_id"]).lower() != "nan"
    }
    store.save_state(state)
    st.success("Adjustments saved.")

# --- Metals ---
st.header("Metals")
st.caption("Purchase log: date, metal (gold/silver), ounces, total cost, source.")
purchases = metals_source.load_purchases(cfg["metals_purchases_csv_path"])
if purchases is None:
    purchases = pd.DataFrame(columns=metals_source.PURCHASE_COLUMNS)
edited_purchases = st.data_editor(
    purchases, num_rows="dynamic", use_container_width=True, key="metals_editor",
)
if st.button("Save metal purchases"):
    metals_source.save_purchases(edited_purchases, cfg["metals_purchases_csv_path"])
    st.success(f"Wrote {len(edited_purchases)} purchases to {cfg['metals_purchases_csv_path']}.")

# --- Watchlist ---
st.header("Watchlist")
st.caption(
    "Assets to track without holding them. Stocks use Yahoo symbols (NVDA, VFV.TO); "
    "crypto uses CoinGecko ids (solana, cardano)."
)
w1, w2, w3 = st.columns([2, 1, 1])
new_symbol = w1.text_input("Symbol / CoinGecko id", key="watch_symbol")
new_kind = w2.selectbox("Kind", ["stock", "crypto"], key="watch_kind")
if w3.button("Add to watchlist") and new_symbol.strip():
    entry = {"symbol": new_symbol.strip(), "kind": new_kind}
    if entry not in state["watchlist"]:
        state["watchlist"].append(entry)
        store.save_state(state)
    st.rerun()
if state["watchlist"]:
    labels = [f"{w['symbol']} ({w['kind']})" for w in state["watchlist"]]
    to_remove = st.multiselect("Remove entries", labels)
    if to_remove and st.button("Remove selected"):
        state["watchlist"] = [
            w for w, lbl in zip(state["watchlist"], labels) if lbl not in to_remove
        ]
        store.save_state(state)
        st.rerun()
else:
    st.info("Watchlist is empty.")

# --- Transactions ledger ---
st.header("Transactions ledger")
st.caption(
    "Your time-stamped buy record (tax evidence). Rows are added automatically by "
    "'Record a buy' on the Investment page; fix mistakes here and save. Note: "
    "deleting a row does NOT undo the holdings update the buy made."
)
tx = store.load_transactions()
edited_tx = st.data_editor(
    tx, num_rows="dynamic", use_container_width=True, key="tx_editor",
)
if st.button("Save ledger"):
    store.save_transactions(edited_tx)
    st.success("Ledger saved.")

# --- Config ---
with st.expander("Config (addresses & settings)"):
    st.write(
        "On-chain addresses and the refresh interval come from `config.json` in the "
        "data directory — edit that file directly. Current settings:"
    )
    st.json({
        "config_found": cfg["config_found"],
        "refresh_interval": cfg["refresh_interval"],
        "btc_addresses": cfg["btc_addresses"],
        "eth_address": cfg["eth_address"],
        "shakepay_csv_path": cfg["shakepay_csv_path"],
        "stocks_holdings_csv_path": cfg["stocks_holdings_csv_path"],
        "metals_purchases_csv_path": cfg["metals_purchases_csv_path"],
    })
