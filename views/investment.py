from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import assets
import config
import history
import prices
import store
from sources import metals as metals_source
from sources import wealthsimple
from ui import cad, sign_pct

cfg = config.load()
data = assets.build(cfg)
alist = data["assets"]

if not alist:
    st.info("No assets yet — add holdings on the Manage Data page.")
    st.stop()

# --- Selection (dashboard row click sets session state; query param deep-links) ---
ids = [a["id"] for a in alist]
by_id = {a["id"]: a for a in alist}


def label(aid):
    a = by_id[aid]
    parts = [a["symbol"] or a["name"]]
    if a["name"] and a["name"] != a["symbol"]:
        parts.append(a["name"])
    if a["account"]:
        parts.append(a["account"])
    if a["watch_only"]:
        parts.append("watch-only")
    return " · ".join(str(p) for p in parts)


preselect = st.session_state.get("selected_asset") or st.query_params.get("asset")
choice = st.selectbox(
    "Investment", ids,
    index=ids.index(preselect) if preselect in ids else 0,
    format_func=label,
)
st.session_state["selected_asset"] = choice
st.query_params["asset"] = choice
asset = by_id[choice]

title = asset["name"]
if asset["account"]:
    title += f" — {asset['account']}"
st.title(title)
if asset["watch_only"]:
    st.caption("Watch-only — not held. Record a buy below to start a position.")

# --- Market ---
st.subheader("Market")
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Price (CAD)", cad(asset["price_cad"]) if asset["price_cad"] is not None else "—")
    if asset["price_usd"] is not None:
        st.caption(f"${asset['price_usd']:,.2f} USD")
with m2:
    if asset["kind"] == "crypto":
        st.metric("24h Change", sign_pct(asset["change_24h_pct"]))
    else:
        st.metric("Day (since open)", sign_pct(asset["change_intraday_pct"]))
with m3:
    if asset["kind"] != "crypto":
        st.metric("Overnight (open vs prev. close)", sign_pct(asset["change_overnight_pct"]))

if asset["kind"] != "cash":
    period = st.radio("Period", list(history.PERIODS), index=2, horizontal=True)
    if asset["kind"] == "crypto":
        hist = history.get_crypto_history(asset["extra"]["coin_id"], period)
        currency_note = "CAD"
    elif asset["kind"] == "metal":
        hist = history.get_stock_history(asset["extra"]["futures_symbol"], period)
        currency_note = f"USD ({asset['extra']['futures_symbol']} futures)"
    else:
        hist = history.get_stock_history(asset["symbol"], period)
        currency_note = "listing currency (USD for US tickers, CAD for .TO)"
    if hist is None or hist.empty:
        st.info("No price history available.")
    else:
        try:
            dark_theme = st.context.theme.type == "dark"
        except Exception:
            dark_theme = False
        accent = "#3987e5" if dark_theme else "#2a78d6"
        chart = (
            alt.Chart(hist)
            .mark_line(color=accent)
            .encode(
                x=alt.X("ts:T", title=None),
                y=alt.Y("price:Q", title=None, scale=alt.Scale(zero=False)),
                tooltip=[
                    alt.Tooltip("ts:T", title="Time"),
                    alt.Tooltip("price:Q", title="Price", format=",.2f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption(f"Prices in {currency_note}.")

# --- About ---
if asset["kind"] == "stock":
    with st.expander("About this investment"):
        info = prices.get_stock_info(asset["symbol"])
        if not info:
            st.info("No details available.")
        else:
            st.markdown(f"**{info.get('longName') or info.get('shortName') or asset['symbol']}**")
            facts = {
                "Type": info.get("quoteType"),
                "Sector": info.get("sector"),
                "Industry": info.get("industry"),
                "Fund family": info.get("fundFamily"),
                "Category": info.get("category"),
                "Currency": info.get("currency"),
                "Market cap": f"{info['marketCap']:,.0f}" if info.get("marketCap") else None,
                "P/E (trailing)": f"{info['trailingPE']:.2f}" if info.get("trailingPE") else None,
                "Dividend yield": f"{info['dividendYield']:.2f}%" if info.get("dividendYield") else None,
                "52w range": (
                    f"{info['fiftyTwoWeekLow']:,.2f} – {info['fiftyTwoWeekHigh']:,.2f}"
                    if info.get("fiftyTwoWeekLow") and info.get("fiftyTwoWeekHigh") else None
                ),
            }
            for k, v in facts.items():
                if v:
                    st.write(f"**{k}:** {v}")
            if info.get("longBusinessSummary"):
                st.caption(info["longBusinessSummary"])
elif asset["kind"] == "crypto":
    with st.expander("About this investment"):
        info = prices.get_coin_info(asset["extra"]["coin_id"])
        if not info:
            st.info("No details available.")
        else:
            st.markdown(f"**{info.get('name')} ({info.get('symbol')})**")
            if info.get("rank"):
                st.write(f"**Market cap rank:** #{info['rank']}")
            if info.get("market_cap_cad"):
                st.write(f"**Market cap:** {cad(info['market_cap_cad'])}")
            if info.get("ath_cad"):
                st.write(f"**All-time high:** {cad(info['ath_cad'])}")
            if info.get("change_7d_pct") is not None:
                st.write(f"**7d change:** {sign_pct(info['change_7d_pct'])}")
            if info.get("change_30d_pct") is not None:
                st.write(f"**30d change:** {sign_pct(info['change_30d_pct'])}")
            if info.get("description"):
                st.caption(info["description"][:1500])

# --- Your position ---
if not asset["watch_only"]:
    st.subheader("Your position")
    p1, p2, p3, p4 = st.columns(4)
    qty = asset["quantity"] or 0
    p1.metric(f"Quantity ({asset['unit']})", f"{qty:,.6f}".rstrip("0").rstrip("."))
    if asset["cost_cad"] is not None and qty > 0:
        p2.metric("Average Buy Price (CAD)", cad(asset["cost_cad"] / qty))
    if asset["cost_cad"] is not None:
        p3.metric("Book Cost (CAD)", cad(asset["cost_cad"]))
    p4.metric("Value (CAD)", cad(asset["value_cad"]))
    if asset["cost_cad"] is not None and asset["cost_cad"] > 0:
        pnl = asset["value_cad"] - asset["cost_cad"]
        st.metric("Unrealized P&L (CAD)", cad(pnl), delta=f"{pnl / asset['cost_cad'] * 100:.2f}%")
    elif asset["kind"] != "cash":
        st.info("Cost basis unknown, so this asset is excluded from P&L totals.")

    if asset["kind"] == "crypto":
        extra = asset["extra"]
        parts = []
        if extra.get("onchain") is not None:
            parts.append(f"on-chain {extra['onchain']:.6f}")
        if extra.get("steth") is not None:
            parts.append(f"Lido stETH {extra['steth']:.6f} (rebases with staking rewards)")
        adj = extra.get("adjustment") or {}
        if adj.get("quantity"):
            parts.append(f"manual adjustment {adj['quantity']:.6f}")
        if parts:
            st.caption("Quantity breakdown: " + " · ".join(parts))
        if extra.get("fetch_failed"):
            st.warning("On-chain balance fetch failed — quantity may be incomplete.")

# --- Tax ---
if not asset["watch_only"] and asset["kind"] != "cash":
    st.subheader("Tax")
    if asset["asset_class"] in (assets.CLASS_CRYPTO, assets.CLASS_METALS):
        st.write("Capital property — dispositions trigger capital gains (50% inclusion rate).")
        if asset["cost_cad"] is not None:
            unrealized = asset["value_cad"] - asset["cost_cad"]
            if unrealized > 0:
                st.write(
                    f"**Unrealized gain:** {cad(unrealized)} → {cad(unrealized * 0.5)} "
                    "taxable if fully disposed today."
                )
            else:
                st.write(f"**Unrealized loss:** {cad(abs(unrealized))}")
        st.caption(
            "Gains are only taxed when you sell/dispose. The transactions ledger below "
            "is your time-stamped record of buy prices for ACB calculations."
        )
    else:
        st.info(
            "Held in TFSA/FHSA: gains are tax-sheltered (FHSA when withdrawn for a "
            "qualifying home purchase), so no capital gains tracking is needed."
        )
    tx = store.load_transactions()
    if not tx.empty:
        mine = tx[tx["symbol"] == asset["symbol"]]
        if not mine.empty:
            st.write("**Recorded buys for this asset:**")
            st.dataframe(mine, use_container_width=True, hide_index=True)

# --- Record a buy ---
if asset["kind"] != "cash":
    st.subheader("Record a buy")
    st.caption(
        "Adds a time-stamped row to the transactions ledger (your tax record) and "
        "updates your holdings so the dashboard reflects the purchase."
    )
    with st.form("buy_form"):
        b1, b2, b3 = st.columns(3)
        buy_date = b1.date_input("Date", value=date.today())
        buy_qty = b2.number_input(f"Quantity ({asset['unit']})", min_value=0.0, format="%.8f")
        buy_price = b3.number_input(
            "Price per unit (CAD)", min_value=0.0,
            value=float(asset["price_cad"] or 0), format="%.4f",
        )
        b4, b5 = st.columns(2)
        buy_account = b4.text_input(
            "Account", value=asset["account"] or ("Ledger" if asset["kind"] == "crypto" else ""),
        )
        buy_note = b5.text_input("Note (e.g. dealer/exchange)", value="")
        submitted = st.form_submit_button("Record buy")

    if submitted:
        if buy_qty <= 0 or buy_price <= 0:
            st.error("Quantity and price must both be greater than zero.")
        else:
            total = buy_qty * buy_price
            store.append_transaction({
                "date": buy_date.isoformat(),
                "asset_class": asset["asset_class"],
                "symbol": asset["symbol"],
                "quantity": buy_qty,
                "price_cad": buy_price,
                "total_cad": total,
                "account": buy_account,
                "note": buy_note,
            })
            if asset["kind"] == "stock":
                holdings = wealthsimple.load_holdings(cfg["stocks_holdings_csv_path"])
                if holdings is None:
                    holdings = pd.DataFrame(columns=wealthsimple.HOLDINGS_COLUMNS)
                account = buy_account or "UNKNOWN"
                mask = (holdings["account"] == account) & (holdings["symbol"] == asset["symbol"])
                if mask.any():
                    holdings.loc[mask, "shares"] += buy_qty
                    holdings.loc[mask, "book_cost_cad"] += total
                else:
                    holdings = pd.concat([holdings, pd.DataFrame([{
                        "account": account, "symbol": asset["symbol"],
                        "shares": buy_qty, "book_cost_cad": total,
                    }])], ignore_index=True)
                wealthsimple.save_holdings(holdings, cfg["stocks_holdings_csv_path"])
            elif asset["kind"] == "metal":
                purchases = metals_source.load_purchases(cfg["metals_purchases_csv_path"])
                if purchases is None:
                    purchases = pd.DataFrame(columns=metals_source.PURCHASE_COLUMNS)
                purchases = pd.concat([purchases, pd.DataFrame([{
                    "date": buy_date.isoformat(), "metal": asset["name"].lower(),
                    "ounces": buy_qty, "total_cost_cad": total,
                    "source": buy_note or "manual",
                }])], ignore_index=True)
                metals_source.save_purchases(purchases, cfg["metals_purchases_csv_path"])
            elif asset["kind"] == "crypto":
                # On-chain stays authoritative; the adjustment covers coins not
                # yet in tracked addresses (e.g. still on Shakepay).
                state = store.load_state()
                adj = state["crypto_adjustments"].setdefault(
                    asset["extra"]["coin_id"], {"quantity": 0.0, "cost_cad": 0.0}
                )
                adj["quantity"] = adj.get("quantity", 0) + buy_qty
                adj["cost_cad"] = adj.get("cost_cad", 0) + total
                store.save_state(state)
            st.success(f"Recorded buy of {buy_qty} {asset['unit']} at {cad(buy_price)}.")
            st.rerun()
