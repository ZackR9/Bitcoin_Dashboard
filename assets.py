"""Unified asset model: one record per investment across all classes.

Both the dashboard watchlist and the per-investment view consume the records
built here; portfolio.summarize consumes them via to_classes(). Keeps the
existing conventions: fail-soft (missing data -> None), cost_cad=None means
"valued but excluded from P&L".
"""

import streamlit as st

import prices
import store
from sources import bitcoin, ethereum, metals, shakepay, wealthsimple

CLASS_CRYPTO = "Crypto"
CLASS_STOCKS = "Stocks/ETFs"
CLASS_METALS = "Metals"
CLASS_CASH = "Cash"

COIN_META = {
    "bitcoin": {"symbol": "BTC", "name": "Bitcoin"},
    "ethereum": {"symbol": "ETH", "name": "Ethereum (incl. stETH)"},
}
METAL_API_SYMBOLS = {"gold": "XAU", "silver": "XAG"}


def pct(new, old):
    """Percent change from old to new; None when either side is unknown/zero."""
    if new is None or old is None or old == 0:
        return None
    return (new - old) / old * 100


def _asset(**kw):
    base = {
        "id": None, "name": None, "symbol": None, "asset_class": None,
        "kind": None,  # stock | crypto | metal | cash
        "account": None, "quantity": None, "unit": None, "cost_cad": None,
        "price_cad": None, "price_usd": None, "value_cad": 0.0,
        "change_intraday_pct": None, "change_overnight_pct": None,
        "change_24h_pct": None, "watch_only": False, "extra": {},
    }
    base.update(kw)
    return base


# --- Crypto ---
def _build_crypto(cfg, state, out):
    adjustments = state["crypto_adjustments"]
    watch_ids = [
        w["symbol"].strip().lower() for w in state["watchlist"] if w["kind"] == "crypto"
    ]
    coin_ids = tuple(dict.fromkeys(
        list(prices.CORE_COINS) + list(adjustments) + watch_ids
    ))
    coin_prices = prices.get_crypto_prices(coin_ids) or {}

    btc_balance = bitcoin.get_balance(tuple(cfg["btc_addresses"]))
    eth_balance, steth_balance = ethereum.get_balances(cfg["eth_address"])
    btc_basis = shakepay.get_cost_basis(cfg["shakepay_csv_path"], "BTC")
    eth_basis = shakepay.get_cost_basis(cfg["shakepay_csv_path"], "ETH")

    def coin_price(coin_id):
        p = coin_prices.get(coin_id) or {}
        return p.get("cad"), p.get("usd"), p.get("cad_24h_change")

    def crypto_cost(source_basis, adj, fetch_failed):
        """Follows the existing convention: None (excluded from P&L) when the
        balance fetch failed or no basis source exists at all."""
        if fetch_failed or (source_basis is None and not adj):
            return None
        return (source_basis["cad_spent"] if source_basis else 0) + adj.get("cost_cad", 0)

    # BTC: on-chain across btc_addresses + manual adjustment.
    adj = adjustments.get("bitcoin", {})
    fetch_failed = bool(cfg["btc_addresses"]) and btc_balance is None
    qty = (btc_balance or 0) + adj.get("quantity", 0)
    cad_p, usd_p, chg = coin_price("bitcoin")
    out.append(_asset(
        id="crypto:bitcoin", name="Bitcoin", symbol="BTC",
        asset_class=CLASS_CRYPTO, kind="crypto", quantity=qty, unit="BTC",
        cost_cad=crypto_cost(btc_basis, adj, fetch_failed),
        price_cad=cad_p, price_usd=usd_p, value_cad=qty * (cad_p or 0),
        change_24h_pct=chg,
        extra={"coin_id": "bitcoin", "onchain": btc_balance, "adjustment": adj,
               "basis": btc_basis, "fetch_failed": fetch_failed},
    ))

    # ETH: on-chain ETH + stETH (rebases, so balance includes staking rewards)
    # + manual adjustment. One row; stETH breakdown kept in extra.
    adj = adjustments.get("ethereum", {})
    fetch_failed = bool(cfg["eth_address"]) and eth_balance is None and steth_balance is None
    qty = (eth_balance or 0) + (steth_balance or 0) + adj.get("quantity", 0)
    eth_cad, eth_usd, eth_chg = coin_price("ethereum")
    steth_cad, _, _ = coin_price("staked-ether")
    value = (
        (eth_balance or 0) * (eth_cad or 0)
        + (steth_balance or 0) * (steth_cad or eth_cad or 0)
        + adj.get("quantity", 0) * (eth_cad or 0)
    )
    out.append(_asset(
        id="crypto:ethereum", name="Ethereum (incl. stETH)", symbol="ETH",
        asset_class=CLASS_CRYPTO, kind="crypto", quantity=qty, unit="ETH",
        cost_cad=crypto_cost(eth_basis, adj, fetch_failed),
        price_cad=eth_cad, price_usd=eth_usd, value_cad=value,
        change_24h_pct=eth_chg,
        extra={"coin_id": "ethereum", "onchain": eth_balance, "steth": steth_balance,
               "steth_price_cad": steth_cad, "adjustment": adj, "basis": eth_basis,
               "fetch_failed": fetch_failed},
    ))

    # Other coins: held purely via manual adjustments, or watch-only.
    for coin_id in coin_ids:
        if coin_id in prices.CORE_COINS:
            continue
        adj = adjustments.get(coin_id, {})
        qty = adj.get("quantity", 0)
        cad_p, usd_p, chg = coin_price(coin_id)
        meta = COIN_META.get(coin_id, {})
        out.append(_asset(
            id=f"crypto:{coin_id}",
            name=meta.get("name", coin_id.replace("-", " ").title()),
            symbol=meta.get("symbol", coin_id),
            asset_class=CLASS_CRYPTO, kind="crypto", quantity=qty, unit="coins",
            cost_cad=adj.get("cost_cad") if adj else None,
            price_cad=cad_p, price_usd=usd_p, value_cad=qty * (cad_p or 0),
            change_24h_pct=chg, watch_only=not adj,
            extra={"coin_id": coin_id, "adjustment": adj},
        ))


# --- Stocks/ETFs ---
def _build_stocks(cfg, state, usd_cad, out):
    holdings = wealthsimple.load_holdings(cfg["stocks_holdings_csv_path"])
    watch_syms = [
        w["symbol"].strip().upper() for w in state["watchlist"] if w["kind"] == "stock"
    ]
    held_syms = (
        list(holdings["symbol"]) if holdings is not None and not holdings.empty else []
    )
    symbols = tuple(dict.fromkeys(held_syms + watch_syms))
    if not symbols:
        return
    quotes = prices.get_stock_quotes(symbols)

    def in_cad(symbol, value):
        q = quotes.get(symbol)
        if value is None or q is None:
            return None
        if q["currency"] == "CAD":
            return value
        if q["currency"] == "USD" and usd_cad:
            return value * usd_cad
        st.warning(f"Unsupported quote currency {q['currency']} for {symbol}")
        return None

    def stock_asset(symbol, **kw):
        q = quotes.get(symbol) or {}
        price_cad = in_cad(symbol, q.get("price"))
        return _asset(
            symbol=symbol, name=symbol, asset_class=CLASS_STOCKS, kind="stock",
            unit="shares", price_cad=price_cad,
            price_usd=q.get("price") if q.get("currency") == "USD" else None,
            change_intraday_pct=pct(q.get("price"), q.get("open")),
            change_overnight_pct=pct(q.get("open"), q.get("previous_close")),
            **kw,
        )

    if holdings is not None:
        for _, row in holdings.iterrows():
            a = stock_asset(
                row["symbol"],
                id=f"stock:{row['account']}:{row['symbol']}",
                account=row["account"], quantity=float(row["shares"]),
            )
            if a["price_cad"] is not None:
                a["value_cad"] = a["price_cad"] * a["quantity"]
                # Unpriced rows keep cost None so a failed quote isn't a fake loss.
                a["cost_cad"] = float(row["book_cost_cad"])
            out.append(a)

    for sym in watch_syms:
        if sym in held_syms:
            continue
        out.append(stock_asset(sym, id=f"watch:stock:{sym}", quantity=0.0, watch_only=True))


# --- Metals ---
def _build_metals(cfg, usd_cad, out):
    purchases = metals.load_purchases(cfg["metals_purchases_csv_path"])
    if purchases is None or purchases.empty:
        return
    for metal_name, pos in metals.summarize(purchases).items():
        api_symbol = METAL_API_SYMBOLS.get(metal_name)
        spot_usd = prices.get_metal_spot_usd(api_symbol) if api_symbol else None
        spot_cad = spot_usd * usd_cad if spot_usd and usd_cad else None
        refs = prices.get_metal_futures_refs(api_symbol) if api_symbol else {}
        if spot_cad is None:
            st.warning(f"No spot price for '{metal_name}'; it is excluded from totals.")
        out.append(_asset(
            id=f"metal:{metal_name}", name=metal_name.title(),
            symbol=api_symbol or metal_name, asset_class=CLASS_METALS, kind="metal",
            quantity=pos["ounces"], unit="oz",
            cost_cad=pos["cost_cad"] if spot_cad is not None else None,
            price_cad=spot_cad, price_usd=spot_usd,
            value_cad=pos["ounces"] * spot_cad if spot_cad is not None else 0,
            change_intraday_pct=pct(refs.get("last"), refs.get("open")),
            change_overnight_pct=pct(refs.get("open"), refs.get("previous_close")),
            extra={"futures_symbol": prices.METAL_FUTURES.get(api_symbol),
                   "avg_cost_per_oz": pos["avg_cost_per_oz"]},
        ))


# --- Cash ---
def _build_cash(cfg, state, out):
    cash = state["cash_cad"] if state["cash_cad"] is not None else cfg["cash_cad"]
    out.append(_asset(
        id="cash", name="Cash (WS Chequing)", symbol="CAD", asset_class=CLASS_CASH,
        kind="cash", quantity=cash, unit="CAD", cost_cad=cash, price_cad=1.0,
        value_cad=cash,
    ))


def build(cfg):
    """All asset records plus the shared context the views need."""
    state = store.load_state()
    usd_cad = prices.get_usd_cad()
    out = []
    _build_crypto(cfg, state, out)
    _build_stocks(cfg, state, usd_cad, out)
    _build_metals(cfg, usd_cad, out)
    _build_cash(cfg, state, out)
    return {"assets": out, "state": state, "usd_cad": usd_cad}


def to_classes(assets_list):
    """Per-asset entries for portfolio.summarize (which aggregates allocation
    by class name); watch-only rows carry no value and are skipped."""
    return [
        {"name": a["asset_class"], "value_cad": a["value_cad"], "cost_cad": a["cost_cad"]}
        for a in assets_list if not a["watch_only"]
    ]
