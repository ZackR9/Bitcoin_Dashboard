import json
import os

CONFIG_PATH = "config.json"


def _read_raw():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def load():
    raw = _read_raw()
    found = raw is not None
    raw = raw or {}

    api = raw.get("api_settings", {})
    crypto = raw.get("crypto", {})
    # Legacy pre-aggregator config shape ("data_sources") still maps in so an
    # existing config.json keeps working.
    legacy = raw.get("data_sources", {})

    btc_addresses = crypto.get("btc_addresses", [])
    if not btc_addresses and legacy.get("ledger_address"):
        btc_addresses = [legacy["ledger_address"]]

    return {
        "config_found": found,
        "refresh_interval": api.get("refresh_interval", 300),
        "cash_cad": raw.get("cash", {}).get("chequing_cad", 0),
        "shakepay_csv_path": crypto.get("shakepay_csv_path") or legacy.get("shakepay_csv_path"),
        "btc_addresses": btc_addresses,
        "eth_address": crypto.get("eth_address", ""),
        "stocks_holdings_csv_path": raw.get("stocks", {}).get("holdings_csv_path"),
        "metals_purchases_csv_path": raw.get("metals", {}).get("purchases_csv_path"),
    }


REFRESH_INTERVAL = load()["refresh_interval"]
