# Portfolio Dashboard

Single-page Streamlit dashboard aggregating all investments, CAD-first: cash
(Wealthsimple chequing), stocks/ETFs (Wealthsimple TFSA/FHSA), BTC and ETH
(bought on Shakepay, held on Ledger), ETH staked via Lido (stETH), and physical
gold/silver.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Required local files (all gitignored, never committed)

### config.json

```json
{
  "api_settings": { "refresh_interval": 300 },
  "cash":   { "chequing_cad": 0 },
  "crypto": {
    "shakepay_csv_path": "shakepay.csv",
    "btc_addresses": ["bc1..."],
    "eth_address": "0x..."
  },
  "stocks": { "holdings_csv_path": "ws_holdings.csv" },
  "metals": { "purchases_csv_path": "metals_purchases.csv" }
}
```

The legacy `data_sources` shape (single `ledger_address`) still loads.

### Data CSVs

- **Shakepay export** — downloaded from Shakepay; `Buy` rows for BTC/ETH provide
  cost basis.
- **`ws_holdings.csv`** — user-maintained stock holdings:
  `account,symbol,shares,book_cost_cad`. Symbols in Yahoo format (`VFV.TO`).
  Can be regenerated in-app by uploading a Wealthsimple activity export
  (Stocks tab; previous file is backed up as `.bak`).
- **`metals_purchases.csv`** — physical metal purchase log:
  `date,metal,ounces,total_cost_cad,source` (`metal` is `gold`/`silver`).

## Where each number comes from

| Asset | Balance | Price | Cost basis |
|---|---|---|---|
| BTC | Blockstream (sum over `btc_addresses`) | CoinGecko | Shakepay CSV |
| ETH + stETH | Blockscout (ETH + Lido stETH token balance) | CoinGecko | Shakepay CSV |
| Stocks/ETFs | holdings CSV | Yahoo Finance (yfinance) | holdings CSV |
| Gold/Silver | purchases CSV | gold-api.com × Frankfurter USD/CAD | purchases CSV |
| Cash | config.json | — | — |

All external APIs are free and keyless.

TODO — full xpub/zpub derivation would cover unknown change addresses; the
current mitigation is listing addresses explicitly in `btc_addresses`.
