# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Streamlit dashboard aggregating one person's investments CAD-first: cash (Wealthsimple chequing), stocks/ETFs (Wealthsimple TFSA/FHSA), BTC/ETH (bought on Shakepay, held on Ledger), Lido-staked ETH (stETH), and physical gold/silver. There is no test suite, linter, or package config.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Layout

- [app.py](app.py) — UI only: overview metrics + allocation chart, then tabs (Crypto | Stocks | Metals | Cash | Tax). All cross-class math is fed by the modules below.
- [config.py](config.py) — loads `config.json` with defaults; maps the legacy `data_sources` shape (single `ledger_address`) into the current one. Exposes module-level `REFRESH_INTERVAL` used as the `st.cache_data` ttl everywhere.
- [prices.py](prices.py) — cached price fetchers: CoinGecko (BTC/ETH/stETH, CAD+USD), yfinance stock quotes, gold-api.com metal spot (USD/oz), Frankfurter USD→CAD. Note Frankfurter's `.app` domain is dead; only `api.frankfurter.dev` works.
- [portfolio.py](portfolio.py) — totals/P&L/allocation across asset classes. Classes with unknown cost basis (`cost_cad=None`, e.g. a failed balance fetch) are valued but excluded from P&L; cash passes `cost_cad == value_cad` so it counts as invested with zero return.
- `sources/` — one module per data source: `bitcoin.py` (Blockstream, sums a list of addresses), `ethereum.py` (Blockscout ETH balance + stETH ERC-20 balance; stETH rebases so balance already includes staking rewards), `shakepay.py` (cost basis per asset from Buy rows), `wealthsimple.py` (holdings CSV load/save + tolerant Wealthsimple-export parser), `metals.py` (purchase log aggregation).

## Required local files (all gitignored)

See [README.md](README.md) for full shapes:

- `config.json` — the only configuration mechanism; missing file only warns, app renders degraded.
- Shakepay export CSV — `Type == 'Buy'` rows with `Asset Credited` BTC/ETH provide cost basis (`Book Cost` column).
- Holdings CSV (`account,symbol,shares,book_cost_cad`) — source of truth for stocks; Yahoo symbols. The Stocks tab uploader can regenerate it from a Wealthsimple activity export (backs up to `.bak` first; parser is best-effort because WS export columns drift — see `EXPORT_COLUMN_CANDIDATES`).
- Metals CSV (`date,metal,ounces,total_cost_cad,source`).

## Data-flow caveat

On-chain balances (Blockstream/Blockscout) and Shakepay cost basis are independent sources joined by arithmetic only; numbers line up only if all coins were bought on Shakepay and withdrawn to the configured addresses. The app surfaces this in the Crypto tab.

## Known limitation

BTC balance sums an explicit `btc_addresses` list; full xpub/zpub derivation (covering unknown change addresses) remains future work per README.

## Conventions

- Sections delimited by `# --- Name ---` comments.
- External calls fail soft: catch, `st.warning`/`st.error`, substitute zero/`None` so the page always renders.
- Every network fetcher is wrapped in `@st.cache_data(ttl=REFRESH_INTERVAL)`; cache args must stay hashable (address lists are passed as tuples).
- All money displayed CAD-first (Canadian tax context); USD is informational.
- Tax tab covers capital property only (crypto + metals); TFSA/FHSA gains are tax-sheltered and excluded.
