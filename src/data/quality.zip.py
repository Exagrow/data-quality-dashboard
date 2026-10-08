"""Bundle the committed data quality results into the archive the Data Quality tab reads.

Observable Framework runs this at build time and serves its stdout as data/quality.zip;
the page pulls quality.parquet, rules.json, months.json, volume.json, examples.json and
meta.json out of it. No network: scripts/fetch_tlc.py ran the row rules while each
month's trip file was on disk, and its results live in data/tlc/YYYY-MM/. What runs here
is the handful of rules that need more than one month, or something other than the trips:
reconciliation against TLC's own aggregates, daily volume, publication lag, schema drift.
"""

import calendar
import csv
import io
import json
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tlc"
MONTH = re.compile(r"\d{4}-\d{2}")
sys.path.insert(0, str(ROOT / "scripts"))
import quality_rules as rules  # noqa: E402


def result(rule, month, company, status, value, detail):
    return {"rule": rule, "month": month, "company": company, "status": status, "value": value, "detail": detail}


def days_in(month):
    year, mon = map(int, month.split("-"))
    return calendar.monthrange(year, mon)[1]


def reference():
    """TLC's own monthly counts: the aggregate report by company, the indicators in total."""
    aggregate, indicators = {}, {}
    path = DATA / "reference" / "fhv_base_aggregate.csv"
    if path.exists():
        for r in csv.DictReader(open(path)):
            month = f"{int(r['year'])}-{int(r['month']):02d}"
            aggregate[(month, r["base_license_number"].title())] = int(r["total_dispatched_trips"])
    path = DATA / "reference" / "tlc_monthly_indicators.csv"
    if path.exists():
        for r in csv.DictReader(open(path)):
            indicators[r["Month/Year"]] = int(r["Trips Per Day"].replace(",", "")) * days_in(r["Month/Year"])
    return aggregate, indicators


def reconcile(months, facts, aggregate, indicators):
    """ACC-02 and TML-02: the trip file against the aggregate report and the indicators."""
    out = []
    for m in months:
        trips = facts[m]["trips"]
        for company in ("Uber", "Lyft"):
            ours, theirs = trips.get(company, 0), aggregate.get((m, company))
            if theirs is None:
                out.append(result("ACC-02", m, company, "pending", None, "The aggregate report has no row for this month yet."))
                continue
            diff = ours - theirs
            status = "fail" if abs(diff) > rules.RECONCILE_TOLERANCE * theirs else "pass"
            detail = (f"Trip file {ours:,}; aggregate report {theirs:,}. " +
                      ("They match to the trip." if diff == 0 else f"The file has {abs(diff):,} {'more' if diff > 0 else 'fewer'} ({abs(diff) / theirs:.2%})."))
            out.append(result("ACC-02", m, company, status, diff / theirs, detail))
        total, theirs = sum(trips.values()), indicators.get(m)
        if theirs is None:
            out.append(result("ACC-02", m, "Both", "pending", None, "The monthly indicators have no row for this month yet."))
        else:
            diff = total - theirs
            status = "fail" if abs(diff) > rules.RECONCILE_TOLERANCE * theirs else "pass"
            detail = (f"Trip file {total:,}; monthly indicators about {theirs:,} (trips per day times days). "
                      f"The file has {abs(diff):,} {'more' if diff > 0 else 'fewer'} ({abs(diff) / theirs:.2%}).")
            out.append(result("ACC-02", m, "Both", status, diff / theirs, detail))
        present = all((m, c) in aggregate for c in ("Uber", "Lyft"))
        out.append(result("TML-02", m, "Both", "pass" if present else "fail", None,
                          "The aggregate report covers this month." if present
                          else f"The trip file was published {facts[m]['published']}; the aggregate report still has no row for the month."))
    return out


def volume(con, months):
    """RSN-01: each day's trips against the median of the same weekday within four weeks
    either side. Returns the month results and the daily series the page draws."""
    files = [str(DATA / m / "daily.parquet") for m in months]
    rows = con.execute(f"""
        WITH d AS (SELECT day::DATE AS day, month, company, sum(trips)::BIGINT AS trips
                   FROM read_parquet({files!r}) GROUP BY ALL)
        SELECT strftime(a.day, '%Y-%m-%d'), a.month, a.company, a.trips,
               (SELECT median(b.trips) FROM d b
                 WHERE b.company = a.company AND b.day <> a.day AND isodow(b.day) = isodow(a.day)
                   AND abs(date_diff('day', a.day, b.day)) <= 28) AS expected
        FROM d a ORDER BY a.day, a.company
    """).fetchall()
    series, flagged = [], {}
    for day, month, company, trips, expected in rows:
        deviation = trips / expected - 1 if expected else None
        low = deviation is not None and deviation < -rules.VOLUME_DROP
        cause = rules.KNOWN_VOLUME_CAUSES.get(day) if low else None
        series.append({"day": day, "month": month, "company": company, "trips": trips,
                       "expected": round(expected) if expected else None,
                       "deviation": round(deviation, 4) if deviation is not None else None,
                       "flag": ("explained" if cause else "unexplained") if low else None, "cause": cause})
        if low:
            flagged.setdefault((month, company), []).append((day, deviation, cause))
    out = []
    for m in months:
        for company in ("Uber", "Lyft"):
            hits = flagged.get((m, company), [])
            unexplained = [h for h in hits if not h[2]]
            if not hits:
                detail = "No day more than 25 percent under its expected volume."
            else:
                detail = " ".join(f"{day}: {dev:+.0%}" + (f" ({cause})." if cause else " (no known cause).") for day, dev, cause in hits)
            out.append(result("RSN-01", m, company, "fail" if unexplained else "pass", len(unexplained), detail))
    return out, series


def file_rules(months, facts):
    """TML-01, INT-03 and VAL-10: rules over what each month's file is, not what is in it."""
    out, previous = [], None
    for m in months:
        f = facts[m]
        lag = f.get("lag_days")
        if lag is None:
            out.append(result("TML-01", m, "Both", "pending", None, "No publication date was recorded for this file."))
        else:
            out.append(result("TML-01", m, "Both", "fail" if lag > rules.PUBLICATION_LAG_DAYS else "pass", lag,
                              f"Published {f['published']}, {lag} days after the month ended."))
        unknown = {k: v for k, v in f["rows_by_license"].items() if k not in rules.DOCUMENTED_LICENSES}
        seen = ", ".join(f"{rules.DOCUMENTED_LICENSES.get(k, k)} ({k})" for k in f["rows_by_license"])
        out.append(result("INT-03", m, "Both", "fail" if unknown else "pass", sum(unknown.values()),
                          f"Undocumented codes: {unknown}." if unknown else f"Codes in the file: {seen}."))
        schema = f["schema"]
        problems = []
        if schema != rules.EXPECTED_SCHEMA:
            ours, theirs = dict(map(tuple, schema)), dict(map(tuple, rules.EXPECTED_SCHEMA))
            problems += [f"{c} is not in the dictionary" for c in ours if c not in theirs]
            problems += [f"{c} is in the dictionary and not in the file" for c in theirs if c not in ours]
            problems += [f"{c} is {ours[c]}, expected {theirs[c]}" for c in ours if c in theirs and ours[c] != theirs[c]]
            if not problems:
                problems.append("the columns are in a different order")
        if previous is not None and schema != previous:
            problems.append("the schema changed from the month before")
        out.append(result("VAL-10", m, "Both", "fail" if problems else "pass", len(problems),
                          "; ".join(problems).capitalize() + "." if problems else f"{len(schema)} columns, as the dictionary describes and as the month before."))
        previous = schema
    return out


def main():
    # Finished months only: fetch_tlc.py builds a month in a dot-prefixed directory first.
    # Whole months only, too: a month summarised before the quality rules existed has no
    # results, and a month retired by an older checkout can leave results with no summary.
    # Either is skipped here until fetch_tlc.py writes the month again.
    needed = ("daily.parquet", "quality.parquet", "quality.json", "examples.json")
    months = sorted(p.name for p in DATA.iterdir() if p.is_dir() and MONTH.fullmatch(p.name) and all((p / f).exists() for f in needed))
    if not months:
        raise SystemExit(f"no quality results in {DATA}; run scripts/fetch_tlc.py")

    con = duckdb.connect()
    con.execute("SET threads = 2")
    facts = {m: json.loads((DATA / m / "quality.json").read_text()) for m in months}
    examples = {m: json.loads((DATA / m / "examples.json").read_text()) for m in months}
    aggregate, indicators = reference()
    volume_results, series = volume(con, months)
    month_results = reconcile(months, facts, aggregate, indicators) + volume_results + file_rules(months, facts)

    archive = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        files = [str(DATA / m / "quality.parquet") for m in months]
        path = Path(tmp) / "quality.parquet"
        con.execute(f"COPY (SELECT * FROM read_parquet({files!r}) ORDER BY rule, company, day) TO '{path}' (FORMAT parquet, COMPRESSION zstd)")
        zf.write(path, path.name)
        zf.writestr("rules.json", json.dumps(rules.registry()))
        zf.writestr("months.json", json.dumps({
            "results": month_results,
            "files": [{"month": m, "published": facts[m]["published"], "lag_days": facts[m]["lag_days"],
                       "bytes": facts[m]["file"]["bytes"], "rows": facts[m]["file"]["rows"], "trips": facts[m]["trips"]} for m in months],
        }))
        zf.writestr("volume.json", json.dumps(series))
        zf.writestr("examples.json", json.dumps(examples))
        zf.writestr("meta.json", json.dumps({
            "source": "NYC Taxi & Limousine Commission, High Volume For-Hire Vehicle trip records",
            "source_page": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
            "months": months,
            "rules": len(rules.RULES),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2))
    sys.stdout.buffer.write(archive.getvalue())


if __name__ == "__main__":
    main()
