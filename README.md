# Portfolio Dashboard

Multi-page Streamlit app aggregating all investments, CAD-first: cash
(Wealthsimple chequing), stocks/ETFs (Wealthsimple TFSA/FHSA), BTC and ETH
(bought on Shakepay, held on Ledger), ETH staked via Lido (stETH), and physical
gold/silver.

Pages:

- **Dashboard** — total value / invested / P&L, allocation chart, and the
  watchlist: every holding (plus watch-only tickers) with price, **Day %**
  (since today's open), **Overnight %** (open vs yesterday's close), 24h % for
  crypto, value, P&L and weight. Click a row to open the investment view.
- **Investment** — per-asset detail: price, changes, history chart
  (1D/1W/1M/1Y/Max), asset info, your position (avg buy price, book cost,
  unrealized P&L), tax notes, and **Record a buy** — time-stamps
  date/price/quantity into the transactions ledger (your tax record) *and*
  updates holdings.
- **Manage Data** — everything editable from any device: cash balance, holdings
  table, Wealthsimple/Shakepay export uploads, metal purchases, crypto
  adjustments, watchlist, transactions ledger.
- **Tax** — capital-property summary (crypto + metals), per-asset ACB/gain, and
  the buy ledger. TFSA/FHSA holdings are tax-sheltered and excluded.

## Running

### Docker (recommended — always on)

```bash
mkdir -p data          # then put config.json + CSVs in data/ (see below)
docker compose up -d --build
```

Open <http://localhost:8501>. `restart: unless-stopped` plus Docker Desktop's
**Settings → General → "Start Docker Desktop when you sign in"** makes the
dashboard come back automatically after every reboot.

All user data lives in `./data` (mounted at `/data` in the container), so the
image itself contains no personal information and edits persist across
rebuilds.

### Local (development)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Without a `DATA_DIR` env var, data files are looked up in the repo root.

## Phone access (Tailscale)

1. Install [Tailscale](https://tailscale.com/download) on the PC and on your
   phone, sign both into the same tailnet.
2. On the phone, open `http://<pc-tailscale-name>:8501` (find the machine name
   or 100.x.y.z IP in the Tailscale app).

Traffic stays inside your private tailnet — nothing is exposed to the public
internet. The port is also reachable on your home LAN at `http://<pc-ip>:8501`.
The Manage Data page works from the phone, so you can update balances and
record buys anywhere.

## Data files (all in `data/`, gitignored, never committed)

### config.json — addresses & settings

```json
{
  "api_settings": { "refresh_interval": 300 },
  "crypto": {
    "btc_addresses": ["bc1..."],
    "eth_address": "0x..."
  }
}
```

File paths (`crypto.shakepay_csv_path`, `stocks.holdings_csv_path`,
`metals.purchases_csv_path`) can be overridden but default to the files below
inside `data/`. The legacy `data_sources` shape (single `ledger_address`) and
`cash.chequing_cad` still load.

### Files the app maintains for you

- **`state.json`** — cash balance, watchlist, crypto adjustments (edited via
  Manage Data).
- **`transactions.csv`** — the buy ledger written by "Record a buy":
  `date,asset_class,symbol,quantity,price_cad,total_cad,account,note`.
- **`ws_holdings.csv`** — stock holdings (`account,symbol,shares,book_cost_cad`,
  Yahoo symbols like `VFV.TO`). Editable in-app, or regenerated from a
  Wealthsimple activity export upload.
- **`shakepay.csv`** — Shakepay transactions export, uploaded in-app; `Buy`
  rows provide BTC/ETH cost basis.
- **`metals_purchases.csv`** — physical metal purchase log:
  `date,metal,ounces,total_cost_cad,source` (`metal` is `gold`/`silver`).

Every save backs the previous file up as `.bak`.

## Where each number comes from

| Asset | Balance | Price / changes | Cost basis |
|---|---|---|---|
| BTC | Blockstream (sum over `btc_addresses`) + manual adjustment | CoinGecko (24h change) | Shakepay CSV + adjustments |
| ETH + stETH | Blockscout (ETH + Lido stETH token balance) + manual adjustment | CoinGecko (24h change) | Shakepay CSV + adjustments |
| Stocks/ETFs | holdings CSV | Yahoo Finance (day + overnight from open/prev close) | holdings CSV |
| Gold/Silver | purchases CSV | gold-api.com spot × Frankfurter USD/CAD; day change from GC=F/SI=F futures | purchases CSV |
| Cash | state.json | — | — |

All external APIs are free and keyless.

⚠️ On-chain balances and Shakepay cost basis are independent sources: numbers
line up only if all coins were bought on Shakepay and withdrawn to the
configured addresses. Use crypto adjustments for anything else.

TODO — full xpub/zpub derivation would cover unknown change addresses; the
current mitigation is listing addresses explicitly in `btc_addresses`.
