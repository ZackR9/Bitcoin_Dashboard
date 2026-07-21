from datetime import datetime

import altair as alt
import streamlit as st

import config
import portfolio
import prices
from sources import bitcoin, ethereum, metals, shakepay, wealthsimple

cfg = config.load()

st.set_page_config(page_title="Portfolio Dashboard", page_icon="📊", layout="wide")
st.title("📊 Investment Portfolio")

if not cfg["config_found"]:
    st.warning("Config file 'config.json' not found. Please create it to enable dynamic data loading.")


def cad(x):
    return f"${x:,.2f}"


# --- Prices ---
crypto_prices = prices.get_crypto_prices() or {}
btc_price = crypto_prices.get("bitcoin", {})
eth_price = crypto_prices.get("ethereum", {})
steth_price = crypto_prices.get("staked-ether", {})
usd_cad = prices.get_usd_cad()

# --- Crypto holdings ---
btc_balance = bitcoin.get_balance(tuple(cfg["btc_addresses"]))
eth_balance, steth_balance = ethereum.get_balances(cfg["eth_address"])
btc_basis = shakepay.get_cost_basis(cfg["shakepay_csv_path"], "BTC")
eth_basis = shakepay.get_cost_basis(cfg["shakepay_csv_path"], "ETH")

btc_value_cad = (btc_balance or 0) * btc_price.get("cad", 0)
eth_value_cad = (
    (eth_balance or 0) * eth_price.get("cad", 0)
    + (steth_balance or 0) * steth_price.get("cad", 0)
)
eth_held = (eth_balance or 0) + (steth_balance or 0)

# --- Stocks ---
holdings = wealthsimple.load_holdings(cfg["stocks_holdings_csv_path"])
stocks_value_cad = 0.0
stocks_cost_cad = None
if holdings is not None and not holdings.empty:
    quotes = prices.get_stock_quotes(tuple(holdings["symbol"]))

    def quote_cad(symbol):
        q = quotes.get(symbol)
        if q is None:
            return None
        if q["currency"] == "CAD":
            return q["price"]
        if q["currency"] == "USD" and usd_cad:
            return q["price"] * usd_cad
        st.warning(f"Unsupported quote currency {q['currency']} for {symbol}")
        return None

    holdings = holdings.copy()
    holdings["price_cad"] = holdings["symbol"].map(quote_cad)
    holdings["value_cad"] = holdings["price_cad"] * holdings["shares"]
    holdings["return_cad"] = holdings["value_cad"] - holdings["book_cost_cad"]
    holdings["return_pct"] = holdings["return_cad"] / holdings["book_cost_cad"] * 100
    priced = holdings.dropna(subset=["value_cad"])
    stocks_value_cad = priced["value_cad"].sum()
    # Book cost of unpriced rows is excluded so a failed quote doesn't show as a loss.
    stocks_cost_cad = priced["book_cost_cad"].sum()

# --- Metals ---
purchases = metals.load_purchases(cfg["metals_purchases_csv_path"])
gold_spot_usd = prices.get_metal_spot_usd("XAU")
silver_spot_usd = prices.get_metal_spot_usd("XAG")
spot_cad = {
    "gold": gold_spot_usd * usd_cad if gold_spot_usd and usd_cad else None,
    "silver": silver_spot_usd * usd_cad if silver_spot_usd and usd_cad else None,
}
metals_value_cad = 0.0
metals_cost_cad = None
metals_summary = {}
if purchases is not None and not purchases.empty:
    metals_summary = metals.summarize(purchases)
    metals_cost_cad = 0.0
    for metal, pos in metals_summary.items():
        if spot_cad.get(metal) is not None:
            metals_value_cad += pos["ounces"] * spot_cad[metal]
            metals_cost_cad += pos["cost_cad"]
        else:
            st.warning(f"No spot price for '{metal}'; it is excluded from totals.")

# --- Overview ---
classes = [
    {
        "name": "Bitcoin",
        "value_cad": btc_value_cad,
        "cost_cad": btc_basis["cad_spent"] if btc_basis and btc_balance is not None else None,
    },
    {
        "name": "Ethereum",
        "value_cad": eth_value_cad,
        "cost_cad": eth_basis["cad_spent"] if eth_basis and eth_held > 0 else None,
    },
    {"name": "Stocks/ETFs", "value_cad": stocks_value_cad, "cost_cad": stocks_cost_cad},
    {"name": "Metals", "value_cad": metals_value_cad, "cost_cad": metals_cost_cad},
    {"name": "Cash", "value_cad": cfg["cash_cad"], "cost_cad": cfg["cash_cad"]},
]
summary = portfolio.summarize(classes)

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

crypto_tab, stocks_tab, metals_tab, cash_tab, tax_tab = st.tabs(
    ["₿ Crypto", "📈 Stocks", "🥇 Metals", "💵 Cash", "📋 Tax"]
)

# --- Crypto tab ---
with crypto_tab:
    btc_col, eth_col = st.columns(2)
    with btc_col:
        st.subheader("Bitcoin")
        st.metric("BTC Price (CAD)", cad(btc_price.get("cad", 0)))
        st.caption(f"${btc_price.get('usd', 0):,.2f} USD")
        if btc_balance is not None:
            st.metric("Ledger Balance (BTC)", f"{btc_balance:.8f}")
            st.metric("Value (CAD)", cad(btc_value_cad))
        else:
            st.info("No BTC addresses configured.")
        if btc_basis:
            st.metric("Average Buy Price (Shakepay, CAD)", cad(btc_basis["avg_price"]))
            if btc_balance is not None and btc_basis["cad_spent"] > 0:
                pnl = btc_value_cad - btc_basis["cad_spent"]
                st.metric(
                    "P&L (CAD)", cad(pnl),
                    delta=f"{pnl / btc_basis['cad_spent'] * 100:.2f}%",
                )
    with eth_col:
        st.subheader("Ethereum")
        st.metric("ETH Price (CAD)", cad(eth_price.get("cad", 0)))
        st.caption(
            f"${eth_price.get('usd', 0):,.2f} USD · stETH {cad(steth_price.get('cad', 0))} CAD"
        )
        if eth_balance is not None or steth_balance is not None:
            st.metric("Ledger Balance (ETH)", f"{eth_balance or 0:.6f}")
            st.metric("Lido Staked (stETH)", f"{steth_balance or 0:.6f}")
            st.metric("Value (CAD)", cad(eth_value_cad))
        else:
            st.info("No ETH address configured.")
        if eth_basis:
            st.metric("Average Buy Price (Shakepay, CAD)", cad(eth_basis["avg_price"]))
            if eth_held > 0 and eth_basis["cad_spent"] > 0:
                pnl = eth_value_cad - eth_basis["cad_spent"]
                st.metric(
                    "P&L (CAD)", cad(pnl),
                    delta=f"{pnl / eth_basis['cad_spent'] * 100:.2f}%",
                )
    if not cfg["shakepay_csv_path"]:
        st.error("Shakepay CSV file not found or path not set in config.")
    st.warning(
        "⚠️ On-chain balances and Shakepay cost basis are independent sources: the numbers "
        "only line up if all your BTC/ETH was bought on Shakepay and withdrawn to the "
        "configured addresses. Coins bought elsewhere need manual cost-basis adjustments."
    )

# --- Stocks tab ---
with stocks_tab:
    st.subheader("Wealthsimple TFSA/FHSA")
    if holdings is None:
        st.error("Holdings CSV not found or path not set in config (stocks.holdings_csv_path).")
    elif holdings.empty:
        st.info("Holdings CSV is empty.")
    else:
        st.dataframe(
            holdings,
            use_container_width=True,
            hide_index=True,
            column_config={
                "account": "Account",
                "symbol": "Symbol",
                "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                "book_cost_cad": st.column_config.NumberColumn("Book Cost (CAD)", format="$%.2f"),
                "price_cad": st.column_config.NumberColumn("Price (CAD)", format="$%.2f"),
                "value_cad": st.column_config.NumberColumn("Value (CAD)", format="$%.2f"),
                "return_cad": st.column_config.NumberColumn("Return (CAD)", format="$%.2f"),
                "return_pct": st.column_config.NumberColumn("Return %", format="%.2f%%"),
            },
        )
        for account, group in holdings.groupby("account"):
            value = group["value_cad"].sum()
            cost = group.dropna(subset=["value_cad"])["book_cost_cad"].sum()
            delta = f"{(value - cost) / cost * 100:.2f}%" if cost > 0 else None
            st.metric(f"{account} Value (CAD)", cad(value), delta=delta)

    st.divider()
    st.subheader("Update holdings from a Wealthsimple export")
    st.caption(
        "Upload an activity/transactions CSV exported from Wealthsimple. Buys and sells are "
        "aggregated into per-symbol positions (average-cost basis) and can replace the "
        "holdings CSV. Review the preview first — Wealthsimple symbols may need their Yahoo "
        "suffix added afterwards (e.g. VFV → VFV.TO)."
    )
    uploaded = st.file_uploader("Wealthsimple export CSV", type="csv")
    if uploaded is not None:
        proposed, error = wealthsimple.parse_export(uploaded)
        if error:
            st.error(error)
        else:
            st.write("**Proposed holdings:**")
            st.dataframe(proposed, use_container_width=True, hide_index=True)
            if not cfg["stocks_holdings_csv_path"]:
                st.error("Set stocks.holdings_csv_path in config.json to apply this update.")
            elif st.button("Apply to holdings CSV"):
                wealthsimple.save_holdings(proposed, cfg["stocks_holdings_csv_path"])
                st.success(
                    f"Wrote {len(proposed)} holdings to {cfg['stocks_holdings_csv_path']} "
                    "(previous file backed up as .bak). Reload to see updated values."
                )

# --- Metals tab ---
with metals_tab:
    st.subheader("Physical Gold & Silver")
    spot_col1, spot_col2 = st.columns(2)
    with spot_col1:
        if spot_cad["gold"]:
            st.metric("Gold Spot (CAD/oz)", cad(spot_cad["gold"]))
            st.caption(f"${gold_spot_usd:,.2f} USD/oz")
    with spot_col2:
        if spot_cad["silver"]:
            st.metric("Silver Spot (CAD/oz)", cad(spot_cad["silver"]))
            st.caption(f"${silver_spot_usd:,.2f} USD/oz")
    if purchases is None:
        st.error("Metals CSV not found or path not set in config (metals.purchases_csv_path).")
    elif not metals_summary:
        st.info("No metal purchases recorded.")
    else:
        for metal, pos in metals_summary.items():
            st.markdown(f"**{metal.title()}**")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Ounces", f"{pos['ounces']:.2f}")
            m2.metric("Avg Cost (CAD/oz)", cad(pos["avg_cost_per_oz"]))
            if spot_cad.get(metal) is not None:
                value = pos["ounces"] * spot_cad[metal]
                pnl = value - pos["cost_cad"]
                m3.metric("Value (CAD)", cad(value))
                m4.metric(
                    "P&L (CAD)", cad(pnl),
                    delta=f"{pnl / pos['cost_cad'] * 100:.2f}%" if pos["cost_cad"] > 0 else None,
                )
        with st.expander("Purchase history"):
            st.dataframe(purchases, use_container_width=True, hide_index=True)
        st.caption(
            "Value uses spot price only; dealer premiums paid are part of your cost but "
            "won't be recovered at spot."
        )

# --- Cash tab ---
with cash_tab:
    st.subheader("Wealthsimple Chequing")
    st.metric("Balance (CAD)", cad(cfg["cash_cad"]))
    st.caption("Updated manually in config.json (cash.chequing_cad).")

# --- Tax tab ---
with tax_tab:
    st.subheader("📋 Tax Information (Canada)")
    st.write(f"**Tax Year:** {datetime.now().year}")
    taxable = [c for c in classes if c["name"] in ("Bitcoin", "Ethereum", "Metals")]
    taxable_known = [c for c in taxable if c["cost_cad"] is not None]
    taxable_cost = sum(c["cost_cad"] for c in taxable_known)
    taxable_value = sum(c["value_cad"] for c in taxable_known)
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
    st.info(
        "Stocks/ETFs are excluded: gains inside a TFSA are tax-free and FHSA gains are "
        "tax-free when withdrawn for a qualifying home purchase."
    )
    st.warning(
        "⚠️ If you purchased crypto on other exchanges before Shakepay, you'll need to add "
        "those transactions manually or consult a tax professional for accurate cost basis."
    )

st.markdown("---")
st.caption("⚠️ This tool is for informational purposes only. Consult a tax professional for official tax advice.")

# Run: streamlit run app.py
