# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A multi-page Streamlit dashboard aggregating one person's investments CAD-first: cash (Wealthsimple chequing), stocks/ETFs (Wealthsimple TFSA/FHSA), BTC/ETH (bought on Shakepay, held on Ledger), Lido-staked ETH (stETH), and physical gold/silver. Runs always-on in Docker; reached from the phone via Tailscale. There is no test suite, linter, or package config.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py            # local; data files in repo root
docker compose up -d --build    # production; data files in ./data (DATA_DIR=/data)
```

## Layout

- [app.py](app.py) — entry point only: `st.set_page_config` + `st.navigation` over the four views.
- `views/` — one script per page, all UI:
  - [dashboard.py](views/dashboard.py) — overview metrics + allocation chart + watchlist table (row select → `st.session_state["selected_asset"]` → `st.switch_page` to the investment view).
  - [investment.py](views/investment.py) — per-asset detail: market data, history chart, about info, position, tax notes, and the "Record a buy" form (appends to the transactions ledger AND updates the class's source of truth: stocks → holdings CSV, metals → purchases CSV, crypto → `crypto_adjustments`).
  - [data.py](views/data.py) — Manage Data: cash input, editable holdings/metals/adjustments/ledger tables, WS + Shakepay export uploaders, watchlist add/remove.
  - [tax.py](views/tax.py) — capital-property summary + per-asset ACB + buy ledger.
- [assets.py](assets.py) — the core model: builds one record per investment across all classes (id, symbol, quantity, cost_cad, price_cad, value_cad, change_intraday/overnight/24h, watch_only, extra). Both dashboard and investment views consume it; `to_classes()` feeds `portfolio.summarize`.
- [store.py](store.py) — persistence for user-entered state under DATA_DIR: `state.json` (cash, watchlist, crypto_adjustments) and `transactions.csv` (buy ledger). Atomic writes with `.bak` backups.
- [config.py](config.py) — loads `config.json` (addresses, refresh interval, path overrides) from `DATA_DIR` (env var, default `.`); all data file paths resolve relative to DATA_DIR with defaults, so the app runs with no config at all (on-chain balances disabled). Maps the legacy `data_sources` shape. Exposes module-level `REFRESH_INTERVAL` used as the `st.cache_data` ttl everywhere.
- [prices.py](prices.py) — cached fetchers: CoinGecko (dynamic id list, CAD+USD+24h change, plus per-coin metadata), yfinance quotes (price/open/previous_close → day + overnight changes) and `.info` subsets, gold-api.com metal spot (USD/oz) with GC=F/SI=F futures as day-change reference, Frankfurter USD→CAD. Note Frankfurter's `.app` domain is dead; only `api.frankfurter.dev` works.
- [history.py](history.py) — cached history for charts: yfinance for stocks/futures (listing currency), CoinGecko market_chart for crypto (CAD). `PERIODS` maps 1D/1W/1M/1Y/Max.
- [portfolio.py](portfolio.py) — totals/P&L/allocation; accepts per-asset entries (allocation groups by class name). Entries with unknown cost basis (`cost_cad=None`, e.g. a failed fetch) are valued but excluded from P&L; cash passes `cost_cad == value_cad`.
- [ui.py](ui.py) — `cad()` / `sign_pct()` formatting helpers.
- `sources/` — one module per data source: `bitcoin.py` (Blockstream, sums a list of addresses), `ethereum.py` (Blockscout ETH + stETH; stETH rebases so balance includes staking rewards), `shakepay.py` (cost basis per asset from Buy rows), `wealthsimple.py` (holdings CSV load/save + tolerant export parser — WS columns drift, see `EXPORT_COLUMN_CANDIDATES`), `metals.py` (purchase log load/save/aggregate).

## Data files (all under DATA_DIR, gitignored)

See [README.md](README.md) for full shapes: `config.json` (only warns if missing), `state.json` + `transactions.csv` (app-maintained via store.py), `ws_holdings.csv`, `shakepay.csv`, `metals_purchases.csv`. Every writer backs up the previous file as `.bak` first.

## Data-flow caveats

- On-chain balances (Blockstream/Blockscout) and Shakepay cost basis are independent sources joined by arithmetic only; `crypto_adjustments` in state.json layers manual quantity/cost deltas on top (coins still on Shakepay, bought elsewhere, or other coins entirely — keyed by CoinGecko id).
- "Record a buy" writes the ledger row AND the class source of truth; deleting a ledger row later does not undo the holdings update.
- ETH and stETH are one asset row (`crypto:ethereum`) because the Shakepay cost basis can't be split; the stETH breakdown lives in `extra`.

## Known limitation

BTC balance sums an explicit `btc_addresses` list; full xpub/zpub derivation (covering unknown change addresses) remains future work per README.

## Conventions

- Sections delimited by `# --- Name ---` comments.
- External calls fail soft: catch, `st.warning`/`st.error`, substitute zero/`None` so the page always renders.
- Every network fetcher is wrapped in `@st.cache_data(ttl=REFRESH_INTERVAL)`; cache args must stay hashable (address/symbol/id lists are passed as tuples).
- All money displayed CAD-first (Canadian tax context); USD is informational. History charts for stocks/futures are in listing currency (labeled).
- Tax page covers capital property only (crypto + metals); TFSA/FHSA gains are tax-sheltered and excluded.
- Views are `st.Page` scripts, not functions — they run top to bottom and import the root modules directly.
