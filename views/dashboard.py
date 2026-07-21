import altair as alt
import pandas as pd
import streamlit as st

import assets
import config
import portfolio
from ui import cad

cfg = config.load()

st.title("📊 Investment Portfolio")
if not cfg["config_found"]:
    st.warning(
        "Config file 'config.json' not found in the data directory. On-chain "
        "balances stay disabled until it exists; everything else still works."
    )

data = assets.build(cfg)
alist = data["assets"]
usd_cad = data["usd_cad"]
summary = portfolio.summarize(assets.to_classes(alist))

# --- Overview ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Portfolio Value (CAD)", cad(summary["total_value_cad"]))
    if usd_cad:
        st.caption(f"≈ ${summary['total_value_cad'] / usd_cad:,.2f} USD")
with col2:
    st.metric("Total Invested (CAD)", cad(summary["total_cost_cad"]))
with col3:
    delta = f"{summary['pnl_pct']:.2f}%" if summary["pnl_pct"] is not None else None
    st.metric("Unrealized P&L (CAD)", cad(summary["pnl_cad"]), delta=delta)

if not summary["allocation"].empty:
    try:
        dark_theme = st.context.theme.type == "dark"
    except Exception:
        dark_theme = False
    accent = "#3987e5" if dark_theme else "#2a78d6"
    allocation_chart = (
        alt.Chart(summary["allocation"])
        .mark_bar(color=accent, cornerRadiusEnd=4, size=18)
        .encode(
            x=alt.X("value_cad", title=None, axis=alt.Axis(format="$,.0f")),
            y=alt.Y("asset_class", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("asset_class", title="Asset class"),
                alt.Tooltip("value_cad", title="Value (CAD)", format="$,.2f"),
            ],
        )
        .properties(height=180)
    )
    st.altair_chart(allocation_chart, use_container_width=True)

# --- Watchlist ---
st.subheader("Watchlist")
st.caption(
    "Day % = change since today's open · Overnight % = today's open vs yesterday's "
    "close · crypto trades 24/7 so it shows a rolling 24h change instead. "
    "Select a row to open the investment view."
)

total_value = summary["total_value_cad"] or 0


def to_rows(items):
    rows = []
    for a in items:
        pnl = pnl_pct = None
        if a["cost_cad"] is not None:
            pnl = a["value_cad"] - a["cost_cad"]
            pnl_pct = pnl / a["cost_cad"] * 100 if a["cost_cad"] > 0 else None
        rows.append({
            "id": a["id"],
            "symbol": a["symbol"],
            "name": a["name"],
            "asset_class": a["asset_class"],
            "account": a["account"],
            "price_cad": a["price_cad"],
            "day_pct": a["change_intraday_pct"],
            "overnight_pct": a["change_overnight_pct"],
            "h24_pct": a["change_24h_pct"],
            "quantity": a["quantity"],
            "value_cad": a["value_cad"],
            "pnl_cad": pnl,
            "pnl_pct": pnl_pct,
            "weight_pct": a["value_cad"] / total_value * 100 if total_value else None,
        })
    return pd.DataFrame(rows)


COLUMN_CONFIG = {
    "id": None,
    "symbol": "Symbol",
    "name": "Name",
    "asset_class": "Class",
    "account": "Account",
    "price_cad": st.column_config.NumberColumn("Price (CAD)", format="$%.2f"),
    "day_pct": st.column_config.NumberColumn("Day %", format="%+.2f%%"),
    "overnight_pct": st.column_config.NumberColumn("Overnight %", format="%+.2f%%"),
    "h24_pct": st.column_config.NumberColumn("24h %", format="%+.2f%%"),
    "quantity": st.column_config.NumberColumn("Quantity", format="%.4f"),
    "value_cad": st.column_config.NumberColumn("Value (CAD)", format="$%.2f"),
    "pnl_cad": st.column_config.NumberColumn("P&L (CAD)", format="$%.2f"),
    "pnl_pct": st.column_config.NumberColumn("P&L %", format="%+.2f%%"),
    "weight_pct": st.column_config.NumberColumn("Weight %", format="%.1f%%"),
}


def show_table(items, key, drop_columns=()):
    df = to_rows(items)
    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={**COLUMN_CONFIG, **{c: None for c in drop_columns}},
        on_select="rerun",
        selection_mode="single-row",
        key=key,
    )
    if event.selection.rows:
        st.session_state["selected_asset"] = df.iloc[event.selection.rows[0]]["id"]
        st.switch_page("views/investment.py")


held = [a for a in alist if not a["watch_only"]]
watch = [a for a in alist if a["watch_only"]]

if held:
    show_table(held, "held_table")
else:
    st.info("No holdings yet — add them on the Manage Data page.")

if watch:
    st.subheader("Watching (not held)")
    show_table(watch, "watch_table", drop_columns=("account", "quantity", "value_cad", "pnl_cad", "pnl_pct", "weight_pct"))
