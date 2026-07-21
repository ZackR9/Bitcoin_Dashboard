import json
import os

# All user data (config.json + CSVs + state.json) lives in one directory so it
# can be mounted as a Docker volume. Defaults to the repo root for local runs.
DATA_DIR = os.environ.get("DATA_DIR", ".")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")


def _read_raw():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _resolve(path, default_name):
    """Data file paths are relative to DATA_DIR unless absolute; every file has
    a default name so the app works with no config.json at all."""
    path = path or default_name
    if os.path.isabs(path):
        return path
    return os.path.join(DATA_DIR, path)


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
        # Legacy cash location; store.py's state.json takes precedence when set.
        "cash_cad": raw.get("cash", {}).get("chequing_cad", 0),
        "shakepay_csv_path": _resolve(
            crypto.get("shakepay_csv_path") or legacy.get("shakepay_csv_path"),
            "shakepay.csv",
        ),
        "btc_addresses": btc_addresses,
        "eth_address": crypto.get("eth_address", ""),
        "stocks_holdings_csv_path": _resolve(
            raw.get("stocks", {}).get("holdings_csv_path"), "ws_holdings.csv"
        ),
        "metals_purchases_csv_path": _resolve(
            raw.get("metals", {}).get("purchases_csv_path"), "metals_purchases.csv"
        ),
    }


REFRESH_INTERVAL = load()["refresh_interval"]
