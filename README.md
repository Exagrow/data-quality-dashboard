# data-quality-dashboard

A live data quality dashboard on real public data: [every Uber and Lyft trip
reported to the NYC Taxi & Limousine Commission (TLC)](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). It is the reference
dashboard from the DAMA-MN workshop "Building a Live Data Quality Dashboard with
Claude Code" (October 2026), by [Exagrow](https://exagrow.com).

- **See it running:** https://quality.exagrow.com (three tabs: Operations, Data
  Quality, UI Design Reference)
- **Build your own from scratch**, the way we did in the workshop:
  https://github.com/Exagrow/dashboard-workshop

## Run it

Needs Node 20 or later, and Python 3.12 or 3.13 with [uv](https://github.com/astral-sh/uv).

```bash
npm ci
uv sync
uv run npm run dev        # http://localhost:3000, rebuilds on save
uv run npm run build      # writes dist/, a static site for any host
```

Use `uv run`: the data loaders are Python, and uv puts DuckDB on their path.

## How the data gets here

The pages read small result files in `data/tlc/YYYY-MM/` (about 125 KB a month:
summaries, rule results, a few example records). The raw trip rows never reach the
repo or the site.

```
TLC monthly parquet (≈500 MB, ≈20M trips)
  → scripts/fetch_tlc.py       one full download, summarise, run the quality
                               rules (scripts/quality_rules.py) with DuckDB
  → data/tlc/YYYY-MM/          the results
  → src/data/*.zip.py          data loaders, bundle the latest 12 months
  → dist/                      the static site
```

That folder is filled two ways.

**On Netlify, by itself.** This is how quality.exagrow.com stays current with
nobody pushing:

1. `netlify/functions/monthly-rebuild.mjs` runs on the 3rd of each month and
   triggers a build.
2. `plugins/results-cache` retrieves the months earlier builds computed, from the
   Netlify Blobs store `tlc-results`.
3. `fetch_tlc.py --hosted` computes any month in the window that still has no
   results (at most three a build, newest first) and throws the raw file away. If
   TLC cannot be reached, the build carries on with what it has.
4. The site builds. Once the deploy succeeds,
   `netlify/functions/deploy-succeeded.mjs` copies the results into the Blobs
   store, so no month is ever computed twice.

Nothing is committed back. Months computed this way live in the Blobs store, not
in the repo.

**On your machine, by hand.** `fetch_tlc.py` writes the results into `data/tlc/`
and you commit them. A committed month always wins over a stored one. The twelve
months in this repo arrived this way: they are the starting point for a clone or
a new Netlify site, and they will fall behind the live site as it adds newer ones.

```bash
uv run scripts/fetch_tlc.py           # any missing month among the latest 12
uv run scripts/fetch_tlc.py 2026-06   # re-check one month
uv run scripts/fetch_tlc.py --all     # re-check every month, after changing a rule
```

- Run by hand, raw files are cached in `data/raw/` (git ignores it; about 6 GB for
  a year), so re-checking downloads nothing. `TLC_RAW_DIR` moves the cache.
- DuckDB is capped at 3 GB and four threads (`TLC_MEMORY_LIMIT`, `TLC_THREADS`).
  Its defaults can freeze a desktop on a file this size.
- **Do not read TLC's files over HTTP range requests** (DuckDB `httpfs`). It makes
  hundreds of requests per file and TLC's CDN will block you.

The source is
[TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
(High Volume For-Hire Vehicle records), with no API key or sign-up. TLC publishes
each month about two months behind.

### With a data warehouse, this gets simpler

Most of the above exists because this dashboard has no database: the build itself
has to download the data, run the checks and remember the results. With a data
warehouse fed by an automatic ETL flow, the scheduled rebuild, the Blobs store and
the committed result files all go away. The quality rules run as queries where the
data already lives, and the dashboard only reads the answers.

```
Data Source  →  Data Warehouse  →  Dashboard
              (ETL loads it and    (reads the
               runs the rules)      results)
```

## Deploy

`npm run build` writes a static site for any host. For the self-refreshing setup
above, connect the repository to a Netlify site (`netlify.toml` carries the build)
and set one environment variable there, `BUILD_HOOK_URL`: a build hook for the
site, which the monthly function calls.

## Where things are

- `src/*.md`: the three pages.
- `src/components/`: what is specific to this dashboard (scorecard, rule cards,
  tabs, filters).
- `src/kit/`: layout and chrome any dashboard needs (masthead, KPI tile, chart
  conventions, formatting, the dark and light switch).
- `src/theme/`: every colour, typeface and logo, and nothing else. Restyle the
  dashboard by replacing this folder; `src/theme/NOTICE.txt` lists the steps.
- `scripts/`: the data pipeline and the quality rules.

## Licence

The code is MIT. The trip data is New York City's, `src/theme/` is Exagrow design
(all rights reserved, included for reference), and three icons are Lucide's. The
terms are in [LICENSE.md](LICENSE.md).
