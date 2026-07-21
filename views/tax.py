from datetime import datetime

import streamlit as st

import assets
import config
import store
from ui import cad

cfg = config.load()
data = assets.build(cfg)
alist = data["assets"]

st.title("📋 Tax Information (Canada)")
st.write(f"**Tax Year:** {datetime.now().year}")

# --- Capital property (crypto + metals) ---
taxable = [
    a for a in alist
    if a["asset_class"] in (assets.CLASS_CRYPTO, assets.CLASS_METALS) and not a["watch_only"]
]
known = [a for a in taxable if a["cost_cad"] is not None]
taxable_cost = sum(a["cost_cad"] for a in known)
taxable_value = sum(a["value_cad"] for a in known)
unrealized = taxable_value - taxable_cost

st.write(f"**Cost Basis of Capital Property (crypto + metals):** {cad(taxable_cost)} CAD")
st.write(f"**Fair Market Value:** {cad(taxable_value)} CAD")
if unrealized > 0:
    st.write(f"**Unrealized Capital Gain (50% taxable): {cad(unrealized * 0.5)} CAD**")
    st.info(
        "💡 This is unrealized gain. Capital gains tax only applies when you sell or "
        "dispose of the asset."
    )
else:
    st.write(f"**Unrealized Capital Loss:** {cad(abs(unrealized))} CAD")

excluded = [a for a in taxable if a["cost_cad"] is None]
if excluded:
    st.warning(
        "Excluded (cost basis unknown): "
        + ", ".join(a["name"] for a in excluded)
        + ". Add cost via Manage Data → Crypto adjustments or the purchase logs."
    )

# --- Per-asset breakdown ---
if known:
    st.subheader("Per-asset breakdown")
    for a in known:
        gain = a["value_cad"] - a["cost_cad"]
        st.write(
            f"**{a['name']}** — ACB {cad(a['cost_cad'])} · FMV {cad(a['value_cad'])} · "
            f"{'gain' if gain >= 0 else 'loss'} {cad(abs(gain))}"
        )

st.info(
    "Stocks/ETFs are excluded: gains inside a TFSA are tax-free and FHSA gains are "
    "tax-free when withdrawn for a qualifying home purchase."
)

# --- Buy ledger ---
st.subheader("Recorded buys (time-stamped price evidence)")
tx = store.load_transactions()
if tx.empty:
    st.info(
        "No buys recorded yet. Use 'Record a buy' on the Investment page to lock in "
        "date/price/quantity when you purchase an asset."
    )
else:
    st.dataframe(tx, use_container_width=True, hide_index=True)

st.warning(
    "⚠️ If you purchased crypto on other exchanges before Shakepay, add those via "
    "Manage Data → Crypto adjustments or consult a tax professional for accurate "
    "cost basis."
)
st.markdown("---")
st.caption(
    "⚠️ This tool is for informational purposes only. Consult a tax professional "
    "for official tax advice."
)
