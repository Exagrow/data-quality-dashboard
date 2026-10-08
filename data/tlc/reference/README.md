# Reference aggregates

TLC's own aggregates of the same trip submissions, refreshed by scripts/fetch_tlc.py whenever it
writes a month, and used at build time to reconcile the trip files against them.

- `fhv_base_aggregate.csv`: the FHV Base Aggregate Report on NYC Open Data (dataset 2v9c-2k7f),
  Uber and Lyft rows only. One row per company and month.
- `tlc_monthly_indicators.csv`: the monthly indicators behind TLC's aggregated reports page
  (https://www.nyc.gov/assets/tlc/downloads/csv/data_reports_monthly.csv), the FHV High Volume rows only.

Refreshed 2026-10-05.
