"""One-shot importer: turn raw Shakepay + Wealthsimple exports into the app's
data files under ./data. Standard library only - no pip install needed.

Generates:
  data/config.json      crypto addresses (ETH + every BTC withdrawal address) + refresh interval
  data/shakepay.csv     a copy of the Shakepay export (BTC/ETH cost basis)
  data/ws_holdings.csv  reconstructed stock/ETF positions (account, symbol, shares, book_cost_cad)

Re-runnable: backs up the previous file as .bak before overwriting. Safe to run
again whenever you download fresh exports. NOTE: it overwrites ws_holdings.csv,
so re-running discards any manual edits you made to holdings in the app.

Usage (from the repo root):
    python import_exports.py [SHAKEPAY_CSV] [WS_ACTIVITIES_CSV]

Both paths default to the file names as downloaded, looked up in the current
directory:
    python import_exports.py "crypto_transactions_summary.csv" "activities-export-2026-07-21.csv"
"""

import csv
import json
import os
import re
import shutil
import sys

DATA_DIR = "data"

# Wealthsimple ticker -> Yahoo Finance symbol. TSX-listed names need a .TO
# suffix for yfinance; US-listed names are used as-is (the app converts USD->CAD).
TSX = ["VFV", "XEI", "XEF", "XEQT", "ZEB", "ENB", "CNR", "L", "CCO",
       "VBAL", "XGRO", "ZMMK"]
US = ["NVDA", "UNH", "MSFT", "IREN", "CEG", "PFE", "AMD", "LMT", "SMCI"]
YAHOO_SYMBOL = {**{s: f"{s}.TO" for s in TSX}, **{s: s for s in US}}


def _backup(path):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")


def _num(value):
    """Float from a CSV cell, or None when blank/non-numeric."""
    try:
        return float(str(value).strip())
    except (ValueError, AttributeError):
        return None


def _rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# --- Crypto: addresses from the Shakepay export ---
def build_config(shakepay_csv):
    btc_addresses, seen = [], set()
    eth_address = ""
    for row in _rows(shakepay_csv):
        if row.get("Type") != "Send":
            continue
        desc = row.get("Description") or ""
        m = re.search(r"Bitcoin address (\S+)", desc)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            btc_addresses.append(m.group(1))
        m = re.search(r"Ethereum address (\S+)", desc)
        if m:
            eth_address = m.group(1)

    config = {
        "api_settings": {"refresh_interval": 300},
        "crypto": {"btc_addresses": btc_addresses, "eth_address": eth_address},
    }
    path = os.path.join(DATA_DIR, "config.json")
    _backup(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"config.json: {len(btc_addresses)} BTC addresses, ETH {eth_address or '(none found)'}")


# --- Crypto: Shakepay export is a drop-in for the app's cost-basis source ---
def copy_shakepay(shakepay_csv):
    path = os.path.join(DATA_DIR, "shakepay.csv")
    _backup(path)
    shutil.copyfile(shakepay_csv, path)
    print(f"shakepay.csv: copied from {shakepay_csv}")


# --- Stocks/ETFs: reconstruct current positions from the WS activity export ---
def build_holdings(ws_csv):
    # ISO dates sort chronologically as strings; a stable sort keeps the file's
    # within-day order (e.g. a same-day buy before its sell).
    rows = sorted(_rows(ws_csv), key=lambda r: r.get("transaction_date") or "")

    positions, unmapped = {}, set()
    for r in rows:
        symbol = (r.get("symbol") or "").strip()
        if not symbol:
            continue  # cash movements, interest, etc.
        account = (r.get("account_type") or "").strip()
        sub = (r.get("activity_sub_type") or "").strip().upper()
        qty = _num(r.get("quantity"))
        amount = _num(r.get("net_cash_amount"))
        pos = positions.setdefault((account, symbol), {"shares": 0.0, "book_cost_cad": 0.0})

        if sub == "BUY" and qty is not None:
            pos["shares"] += qty
            pos["book_cost_cad"] += abs(amount) if amount is not None else 0.0
        elif sub == "SELL" and qty is not None and pos["shares"] > 0:
            sold = min(abs(qty), pos["shares"])
            pos["book_cost_cad"] -= pos["book_cost_cad"] / pos["shares"] * sold
            pos["shares"] -= sold
        elif sub == "SUBDIVISION" and qty is not None:
            pos["shares"] += qty  # stock split: more shares, same book cost

    out = []
    for (account, symbol), p in sorted(positions.items()):
        if p["shares"] <= 1e-6:
            continue
        if symbol not in YAHOO_SYMBOL:
            unmapped.add(symbol)
        out.append([account, YAHOO_SYMBOL.get(symbol, symbol),
                    round(p["shares"], 4), round(p["book_cost_cad"], 2)])

    path = os.path.join(DATA_DIR, "ws_holdings.csv")
    _backup(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["account", "symbol", "shares", "book_cost_cad"])
        w.writerows(out)

    print(f"ws_holdings.csv: {len(out)} positions")
    if unmapped:
        print(f"  ! No Yahoo mapping for {sorted(unmapped)} - written as-is, fix in-app.")
    print(f"  {'account':<10}{'symbol':<10}{'shares':>12}{'book_cost_cad':>15}")
    for account, symbol, shares, cost in out:
        print(f"  {account:<10}{symbol:<10}{shares:>12}{cost:>15}")


def main():
    shakepay = sys.argv[1] if len(sys.argv) > 1 else "crypto_transactions_summary.csv"
    ws = sys.argv[2] if len(sys.argv) > 2 else "activities-export-2026-07-21.csv"
    for label, path in [("Shakepay", shakepay), ("Wealthsimple", ws)]:
        if not os.path.exists(path):
            sys.exit(f"{label} export not found: {path}")

    os.makedirs(DATA_DIR, exist_ok=True)
    build_config(shakepay)
    copy_shakepay(shakepay)
    build_holdings(ws)
    print("\nDone. Review the holdings above, then start the app.")


if __name__ == "__main__":
    main()
