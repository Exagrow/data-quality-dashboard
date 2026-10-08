"""Fetch NYC Uber and Lyft trip records one month at a time and keep only summaries.

Source: NYC Taxi & Limousine Commission (TLC) High Volume For-Hire Vehicle trip
records, one parquet file per month (about 20 million trips, 500 MB each),
published about two months behind on no fixed day.

Each month is downloaded once, in a single request, summarised locally with
DuckDB, and checked against the data quality rules in quality_rules.py. The raw
file is then kept in a local cache (data/raw/, which git ignores), so changing a
rule and running it again never asks TLC for the same 500 MB twice. In CI there
is no cache: the file goes to a temporary directory and is deleted.
The summaries and the rule results (a few hundred KB a month) are committed under
data/tlc/YYYY-MM/, so the site build never touches TLC's servers. TLC's CDN blocks
clients that make many requests in a short time, which is exactly what reading the
files over HTTP range requests does; one polite download per month does not.

Two modes:

  local   (the default) keeps the raw files in the cache and reuses them. Its results
          are committed, so a hosted build finds them already there.
  hosted  (--hosted) is for a build that runs with nobody watching. For any month in
          the window with no results, it checks whether TLC has published it, downloads
          it, runs the rules, keeps the small results for this build and throws the raw
          file away. It never fails the build: if TLC cannot be reached or refuses, it
          says so and the site is built from the results already in the repo. It does
          at most HOSTED_MAX_MONTHS months a run (default 3), newest first.

Usage:
  uv run scripts/fetch_tlc.py              # every missing month among the latest 12
  uv run scripts/fetch_tlc.py 2026-05 ...  # specific months (re-summarises them)
  uv run scripts/fetch_tlc.py --all        # every month in the window again, after changing a rule
  uv run scripts/fetch_tlc.py --hosted     # what a hosted build runs before building the site

The cache is filled by downloading, or by copying trip files into it: a copy of
TLC's file, under the name TLC gives it, dropped into data/raw/ means nothing is
downloaded at all. Set TLC_RAW_DIR to keep the cache somewhere else.

Prints the months it wrote, one per line, so a workflow can tell whether anything
changed. When it wrote any, it also refreshes data/tlc/reference/, the small
aggregate reports the trip counts are reconciled against.

No key or token is used anywhere. The trip files and the one small request to NYC Open
Data are both public and anonymous.
"""

import calendar
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality_rules import PREPARE, ROW_RULES, TRIPS_VIEW  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tlc"
ZONES = DATA / "taxi_zone_lookup.csv"
REFERENCE = DATA / "reference"

# TLC_TRIP_URL points the downloads at a mirror of TLC's files ({} is the month).
TRIP_URL = os.environ.get("TLC_TRIP_URL") or "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{}.parquet"
ZONE_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
# TLC's own aggregates of the same submissions, on other hosts: the FHV Base Aggregate
# Report on NYC Open Data (one row per base and month; Uber and Lyft appear as UBER and
# LYFT) and the monthly indicators behind TLC's aggregated reports page (trips per day by
# licence class). Each is one small request.
AGGREGATE_URL = "https://data.cityofnewyork.us/resource/2v9c-2k7f.csv?" + urllib.parse.urlencode({
    "$select": "base_license_number,year,month,total_dispatched_trips,total_dispatched_shared_trips,unique_dispatched_vehicles",
    "$where": "base_license_number in ('UBER','LYFT') AND year >= 2024",
    "$order": "year,month,base_license_number",
})
INDICATORS_URL = "https://www.nyc.gov/assets/tlc/downloads/csv/data_reports_monthly.csv"
# Who TLC's servers are told is asking. Set TLC_USER_AGENT to name your own project and
# a way to reach you, so TLC can tell your requests apart and contact you about them.
USER_AGENT = os.environ.get("TLC_USER_AGENT") or "data-quality-dashboard (+https://github.com/Exagrow/data-quality-dashboard)"
RAW_CACHE = ROOT / "data" / "raw"
KEEP_MONTHS = 12
HOSTED_MAX_MONTHS = int(os.environ.get("HOSTED_MAX_MONTHS", "3"))
EXAMPLES_PER_RULE = 3

# DuckDB's defaults are every core and 80 percent of RAM, which on a desktop is enough to
# push the machine into swap and freeze it (it did, on 2026-09-21). A month needs neither:
# with these limits it spills to disk instead and takes about a minute. Override with
# TLC_MEMORY_LIMIT and TLC_THREADS on a machine with room to spare.
MEMORY_LIMIT = os.environ.get("TLC_MEMORY_LIMIT", "3GB")
THREADS = int(os.environ.get("TLC_THREADS", "4"))

# hvfhs_license_num values for the two companies still operating.
COMPANIES = {"HV0003": "Uber", "HV0005": "Lyft"}


def log(message):
    print(message, file=sys.stderr, flush=True)


def request(url, method="GET"):
    return urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})


def published(month):
    try:
        with urllib.request.urlopen(request(TRIP_URL.format(month), "HEAD"), timeout=30) as response:
            return response.status == 200
    except urllib.error.HTTPError as error:
        # A month that is not published yet is a 403 from the S3 origin. A 403
        # from CloudFront itself means TLC's CDN is blocking this client.
        if error.code in (403, 404) and (error.headers.get("server") or "").lower() == "amazons3":
            return False
        raise SystemExit(f"TLC's CDN refused {TRIP_URL.format(month)} ({error.code}, server "
                         f"{error.headers.get('server')}); if it says blocked, wait and retry later")


def download(url, path):
    """Fetch url to path and return the response headers (Last-Modified is the only
    record of when TLC published a file)."""
    for attempt in range(1, 4):
        try:
            # Write beside the target and rename when complete, so an interrupted
            # download never leaves something that looks like a cached month.
            partial = Path(str(path) + ".partial")
            with urllib.request.urlopen(request(url), timeout=120) as response, open(partial, "wb") as out:
                shutil.copyfileobj(response, out, length=8 * 1024 * 1024)
                headers = dict(response.headers.items())
            partial.replace(path)
            return headers
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise
            log(f"download failed ({error}), retrying in {30 * attempt}s")
            time.sleep(30 * attempt)


def whole_parquet(path):
    """True when the file starts and ends with parquet's magic bytes, which a
    truncated copy does not."""
    with open(path, "rb") as f:
        if f.read(4) != b"PAR1":
            return False
        f.seek(-4, os.SEEK_END)
        return f.read(4) == b"PAR1"


def published_headers(month):
    """TLC's current headers for a month's file, from one HEAD request, or None when
    TLC cannot be reached (offline, or a room sharing one address)."""
    try:
        with urllib.request.urlopen(request(TRIP_URL.format(month), "HEAD"), timeout=30) as response:
            return dict(response.headers.items())
    except (urllib.error.URLError, TimeoutError):
        return None


def fetch_month(month, directory):
    """The month's raw trip file in directory, downloading it unless it is already there.
    Returns the path and the response headers, which are kept beside the file."""
    path = Path(directory) / f"fhvhv_tripdata_{month}.parquet"
    sidecar = path.with_suffix(".parquet.headers.json")
    if path.exists() and sidecar.exists():
        log(f"{month}: using {path}")
        return path, json.loads(sidecar.read_text())
    if path.exists() and whole_parquet(path):
        # A file copied into the cache by hand arrives
        # without its download record. Ask TLC once for the headers; if the sizes
        # agree it is the same file, and the record is written for next time.
        headers = published_headers(month)
        if headers is None:
            log(f"{month}: using {path} (TLC not reachable, so its publication date is unknown)")
            return path, {}
        if int(headers.get("Content-Length", -1)) == path.stat().st_size:
            sidecar.write_text(json.dumps(headers, indent=2))
            log(f"{month}: using {path} (copied in; matches TLC's file)")
            return path, headers
        log(f"{month}: {path} is not the size TLC publishes now, so TLC has replaced the month; downloading it again")
    log(f"{month}: downloading")
    started = time.monotonic()
    headers = download(TRIP_URL.format(month), path)
    sidecar.write_text(json.dumps(headers, indent=2))
    log(f"{month}: {path.stat().st_size / 1e6:.0f} MB in {time.monotonic() - started:.0f}s")
    return path, headers


def previous(month):
    year, mon = map(int, month.split("-"))
    return f"{year - 1}-12" if mon == 1 else f"{year}-{mon - 1:02d}"


def latest_published(cache=None):
    """The newest month TLC has published, and whether TLC itself said so. Offline
    with a cache, the newest cached month stands in, unconfirmed."""
    month = f"{date.today():%Y-%m}"
    try:
        for _ in range(6):
            if published(month):
                return month, True
            month = previous(month)
    except (urllib.error.URLError, TimeoutError) as error:
        cached = sorted(p.name[len("fhvhv_tripdata_"):-len(".parquet")] for p in Path(cache).glob("fhvhv_tripdata_*.parquet")) if cache else []
        if cached:
            log(f"TLC not reachable ({getattr(error, 'reason', error)}); working from the cache, newest month {cached[-1]}")
            return cached[-1], False
        raise SystemExit(f"TLC not reachable ({getattr(error, 'reason', error)}) and no cached trip files to work from")
    raise SystemExit("no TLC trip file found in the last six months (or the CDN is blocking this client)")


def summarise(month, trips_path, con, tmp):
    """Write {daily,hourly,zones}.parquet for one month's trip file into tmp."""
    company_case = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in COMPANIES.items())
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE summary AS
        WITH trips AS (
            SELECT
                CASE t.hvfhs_license_num {company_case} END AS company,
                CAST(t.pickup_datetime AS DATE) AS day,
                isodow(t.pickup_datetime)::INTEGER AS dow,
                hour(t.pickup_datetime)::INTEGER AS hour,
                t.PULocationID::INTEGER AS zone_id,
                coalesce(z.Borough, 'Unknown') AS borough,
                t.base_passenger_fare AS fare,
                t.driver_pay,
                t.tips,
                t.base_passenger_fare + t.tolls + t.bcf + t.sales_tax
                    + t.congestion_surcharge + coalesce(t.airport_fee, 0)
                    + coalesce(t.cbd_congestion_fee, 0) + t.tips AS rider_total,
                t.trip_miles AS miles,
                t.trip_time AS trip_seconds,
                -- Wait is request to pickup. A few records have the request after
                -- the pickup, or waits over two hours; leave those out of the average.
                CASE WHEN t.pickup_datetime >= t.request_datetime
                      AND t.pickup_datetime < t.request_datetime + INTERVAL 2 HOUR
                     THEN date_diff('second', t.request_datetime, t.pickup_datetime) END AS wait_seconds,
                coalesce(t.airport_fee, 0) > 0 AS airport,
                t.shared_match_flag = 'Y' AS shared,
                t.wav_request_flag = 'Y' AS wav
            FROM read_parquet('{trips_path}', union_by_name = true) t
            LEFT JOIN read_csv_auto('{ZONES}') z ON z.LocationID = t.PULocationID
            WHERE t.hvfhs_license_num IN ({", ".join(repr(k) for k in COMPANIES)})
              -- Each file holds the trips that began in its month.
              AND strftime(t.pickup_datetime, '%Y-%m') = '{month}'
        )
        SELECT
            -- Plain ints, doubles and ISO date strings: Arrow in the browser turns
            -- BIGINT into BigInt and dates into epoch numbers, both awkward to chart.
            strftime(day, '%Y-%m-%d') AS day,
            '{month}' AS month,
            dow, hour, zone_id, company, borough,
            count(*)::INTEGER AS trips,
            sum(fare)::DOUBLE AS fares,
            sum(driver_pay)::DOUBLE AS driver_pay,
            sum(tips)::DOUBLE AS tips,
            sum(rider_total)::DOUBLE AS rider_total,
            sum(miles)::DOUBLE AS miles,
            sum(trip_seconds)::DOUBLE AS trip_seconds,
            sum(wait_seconds)::DOUBLE AS wait_seconds,
            count(wait_seconds)::INTEGER AS wait_trips,
            (count(*) FILTER (WHERE airport))::INTEGER AS airport_trips,
            (count(*) FILTER (WHERE shared))::INTEGER AS shared_trips,
            (count(*) FILTER (WHERE wav))::INTEGER AS wav_trips
        FROM trips
        GROUP BY GROUPING SETS (
            (day, company, borough),
            (company, borough, dow, hour),
            (company, borough, zone_id)
        )
    """)
    measures = """trips, fares, driver_pay, tips, rider_total, miles, trip_seconds,
                  wait_seconds, wait_trips, airport_trips, shared_trips, wav_trips"""
    tables = {
        "daily": f"""SELECT day, month, company, borough, {measures} FROM summary
                     WHERE day IS NOT NULL ORDER BY day, company, borough""",
        "hourly": """SELECT month, company, borough, dow, hour, trips, fares, wait_seconds, wait_trips
                     FROM summary WHERE hour IS NOT NULL ORDER BY company, borough, dow, hour""",
        "zones": f"""SELECT s.month, s.company, s.zone_id, z.Zone AS zone, s.borough, {measures}
                     FROM summary s LEFT JOIN read_csv_auto('{ZONES}') z ON z.LocationID = s.zone_id
                     WHERE s.zone_id IS NOT NULL ORDER BY s.company, s.trips DESC""",
    }
    for name, query in tables.items():
        con.execute(f"COPY ({query}) TO '{tmp / name}.parquet' (FORMAT parquet, COMPRESSION zstd)")
    return con.execute("SELECT sum(trips) FROM summary WHERE day IS NOT NULL").fetchone()[0]


def plain(value):
    """A DuckDB value as JSON-friendly data."""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def check_quality(month, trips_path, con, headers, tmp):
    """Run the row rules over one month's trip file and write, into tmp:

    quality.parquet   one row per day, company and rule: trips that failed it and trips
                      it was checked against
    examples.json     up to EXAMPLES_PER_RULE failing records per rule, the columns the
                      rule names, chosen by a hash so a rerun picks the same ones
    quality.json      facts about the file itself, for the rules that run over a month
                      at build time: when it was published, its size, its schema, its
                      rows by licence code
    """
    con.execute(f"CREATE OR REPLACE TEMP VIEW trips AS {TRIPS_VIEW.format(trips_path=trips_path)}")
    con.execute(f"CREATE OR REPLACE TEMP TABLE zones AS SELECT LocationID FROM read_csv_auto('{ZONES}')")
    for name, query in PREPARE.items():
        con.execute(f"CREATE OR REPLACE TEMP TABLE {name} AS {query}")
    sql = {r.id: r.sql.replace("{month}", month) for r in ROW_RULES if r.sql}

    # Every predicate rule in one pass, then unpivoted to a row per rule.
    counts = ", ".join(
        f"count(*) FILTER (WHERE {sql[r.id]}) AS \"{r.id}\", count(*) FILTER (WHERE {r.applies}) AS \"{r.id}:checked\""
        for r in ROW_RULES if r.sql
    )
    # A trip can fail several rules, so rule counts cannot be added up. These count each
    # trip once: trips failing at least one rule of a dimension and verdict, and of a
    # verdict overall. They are stored beside the rules under ids that start with @.
    rollups = {}
    for r in ROW_RULES:
        if r.sql:
            rollups.setdefault(f"@{r.dimension}/{r.verdict}", []).append(sql[r.id])
            rollups.setdefault(f"@all/{r.verdict}", []).append(sql[r.id])
    counts += ", " + ", ".join(
        f"count(*) FILTER (WHERE {' OR '.join(f'({p})' for p in predicates)}) AS \"{name}\""
        for name, predicates in rollups.items()
    )
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE frame AS
        SELECT company, day, count(*) AS trips, {counts} FROM trips GROUP BY company, day
    """)
    con.execute("CREATE OR REPLACE TEMP TABLE results (company VARCHAR, day DATE, rule VARCHAR, failed INTEGER, checked INTEGER)")
    for r in ROW_RULES:
        if r.sql:
            con.execute(f'INSERT INTO results SELECT company, day, \'{r.id}\', "{r.id}", "{r.id}:checked" FROM frame')
        else:
            # A rule over groups of rows; checked against every trip that day.
            con.execute(f"""
                INSERT INTO results
                SELECT f.company, f.day, '{r.id}', coalesce(g.failed, 0), f.trips
                FROM frame f LEFT JOIN ({r.group_sql}) g ON g.company = f.company AND g.day = f.day
            """)
    for name in rollups:
        con.execute(f'INSERT INTO results SELECT company, day, \'{name}\', "{name}", trips FROM frame')
    con.execute(f"""
        COPY (SELECT '{month}' AS month, strftime(day, '%Y-%m-%d') AS day, company, rule, failed::INTEGER AS failed, checked::INTEGER AS checked
              FROM results ORDER BY rule, company, day)
        TO '{tmp / "quality.parquet"}' (FORMAT parquet, COMPRESSION zstd)
    """)

    examples = {}
    failed = {rule: n for rule, n in con.execute("SELECT rule, sum(failed) FROM results WHERE rule[1] <> '@' GROUP BY rule").fetchall()}
    for r in ROW_RULES:
        if not r.sql or not failed.get(r.id):
            continue
        cols = ", ".join(r.columns)
        rows = con.execute(f"""
            SELECT {cols} FROM trips WHERE {sql[r.id]}
            ORDER BY hash(request_datetime, pickup_datetime, PULocationID, DOLocationID, trip_miles)
            LIMIT {EXAMPLES_PER_RULE}
        """).fetchall()
        examples[r.id] = [dict(zip(r.columns, map(plain, row))) for row in rows]
    (tmp / "examples.json").write_text(json.dumps(examples, indent=1))

    year, mon = map(int, month.split("-"))
    month_end = date(year, mon, calendar.monthrange(year, mon)[1])
    published = parsedate_to_datetime(headers["Last-Modified"]).astimezone(timezone.utc) if headers.get("Last-Modified") else None
    facts = {
        "month": month,
        "file": {
            "url": TRIP_URL.format(month),
            "bytes": os.path.getsize(trips_path),
            "last_modified": published.isoformat(timespec="seconds") if published else None,
            "created_by": con.execute(f"SELECT created_by FROM parquet_file_metadata('{trips_path}')").fetchone()[0],
            "rows": con.execute(f"SELECT count(*) FROM read_parquet('{trips_path}')").fetchone()[0],
        },
        "published": published.date().isoformat() if published else None,
        "lag_days": (published.date() - month_end).days if published else None,
        "rows_by_license": dict(con.execute(f"SELECT hvfhs_license_num, count(*) FROM read_parquet('{trips_path}') GROUP BY 1 ORDER BY 1").fetchall()),
        "schema": [[name, kind] for name, kind, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{trips_path}')").fetchall()],
        "trips": dict(con.execute("SELECT company, sum(trips)::BIGINT FROM frame GROUP BY 1 ORDER BY 1").fetchall()),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (tmp / "quality.json").write_text(json.dumps(facts, indent=1))
    return failed


def write_month(month, trips_path, con, headers):
    """Summaries and quality results for one month, written together or not at all."""
    out = DATA / month
    tmp = DATA / f".{month}.partial"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    trips = summarise(month, trips_path, con, tmp)
    failed = check_quality(month, trips_path, con, headers, tmp)
    shutil.rmtree(out, ignore_errors=True)
    tmp.rename(out)
    return trips, failed


def refresh_reference():
    """Refresh the aggregate reports the trip counts are reconciled against. Both are
    trimmed to the rows the dashboard uses, so the committed files stay a few KB."""
    REFERENCE.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request(AGGREGATE_URL), timeout=60) as response:
        (REFERENCE / "fhv_base_aggregate.csv").write_bytes(response.read())
    with urllib.request.urlopen(request(INDICATORS_URL), timeout=60) as response:
        text = response.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = [r for r in reader if r["License Class"] == "FHV - High Volume" and r["Month/Year"] >= "2024-01"]
    with open(REFERENCE / "tlc_monthly_indicators.csv", "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["Month/Year", "License Class", "Trips Per Day", "Unique Drivers", "Unique Vehicles", "Trips Per Day Shared"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["Month/Year"]))
    (REFERENCE / "README.md").write_text(
        "# Reference aggregates\n\n"
        "TLC's own aggregates of the same trip submissions, refreshed by scripts/fetch_tlc.py whenever it\n"
        "writes a month, and used at build time to reconcile the trip files against them.\n\n"
        f"- `fhv_base_aggregate.csv`: the FHV Base Aggregate Report on NYC Open Data (dataset 2v9c-2k7f),\n"
        f"  Uber and Lyft rows only. One row per company and month.\n"
        f"- `tlc_monthly_indicators.csv`: the monthly indicators behind TLC's aggregated reports page\n"
        f"  ({INDICATORS_URL}), the FHV High Volume rows only.\n\n"
        f"Refreshed {date.today().isoformat()}.\n"
    )


def connect(spill_dir):
    """A DuckDB connection that stays inside the limits above and spills past them."""
    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
    con.execute(f"SET threads = {THREADS}")
    con.execute(f"SET temp_directory = '{Path(spill_dir) / 'duckdb_spill'}'")
    con.execute("SET preserve_insertion_order = false")
    con.execute("SET TimeZone = 'UTC'")
    return con


def main():
    hosted = "--hosted" in sys.argv[1:]
    if not hosted:
        return run(hosted=False)
    # A hosted build must come out the other end whatever TLC does. Months finished
    # before a failure keep their results; the rest wait for the next build.
    try:
        run(hosted=True)
    except SystemExit as stop:
        if stop.code not in (None, 0):
            log(f"hosted refresh stopped early: {stop.code}. Building from the results already here.")
    except Exception as error:  # noqa: BLE001 - nothing here may fail the build
        log(f"hosted refresh stopped early: {type(error).__name__}: {error}. Building from the results already here.")


def run(hosted):
    DATA.mkdir(parents=True, exist_ok=True)
    if not ZONES.exists():
        download(ZONE_URL, ZONES)

    # Local: the raw files are kept in a cache and reused. Hosted, or in CI: there is
    # nowhere to keep them between runs, so each goes to a temporary directory and is
    # deleted once its results are written.
    if hosted:
        raw_dir = None
    else:
        raw_dir = os.environ.get("TLC_RAW_DIR") or (None if os.environ.get("CI") else str(RAW_CACHE))
    if raw_dir:
        Path(raw_dir).mkdir(parents=True, exist_ok=True)
    log(f"mode: {'hosted (no cache, best effort)' if hosted else 'local, raw cache at ' + raw_dir if raw_dir else 'CI (no cache)'}")

    args = [a for a in sys.argv[1:] if a not in ("--all", "--hosted")]
    if args:
        months = args
    else:
        latest, confirmed = latest_published(raw_dir)
        wanted = [latest]
        while len(wanted) < KEEP_MONTHS:
            wanted.append(previous(wanted[-1]))
        # --all runs every month in the window again: the way to see a changed rule everywhere.
        months = sorted(wanted) if "--all" in sys.argv[1:] else sorted(m for m in wanted if not (DATA / m / "quality.parquet").exists())
        # Month directories are YYYY-MM; reference/ is not a month. Nothing is removed
        # on an unconfirmed window: offline, "not in the window" may just mean newer.
        for stale in sorted(p.name for p in DATA.iterdir() if confirmed and p.is_dir() and p.name[:1].isdigit() and p.name not in wanted):
            shutil.rmtree(DATA / stale)
            log(f"removed {stale} (older than the latest {KEEP_MONTHS} months)")
        if hosted and len(months) > HOSTED_MAX_MONTHS:
            # Newest first: a build has minutes, not an hour, and the newest months are
            # the ones a visitor notices missing.
            log(f"{len(months)} months have no results; doing the newest {HOSTED_MAX_MONTHS} this build, the rest next time")
            months = months[-HOSTED_MAX_MONTHS:]
        if hosted and not months:
            log("every month in the window already has results; nothing to fetch")

    for month in months:
        with tempfile.TemporaryDirectory() as tmp:
            path, headers = fetch_month(month, raw_dir or tmp)
            started = time.monotonic()
            # A connection per month, so one month's memory is given back before the next.
            with connect(tmp) as con:
                trips, failed = write_month(month, path, con, headers)
            flagged = sum(1 for n in failed.values() if n)
            log(f"{month}: {trips:,} trips, {flagged} of {len(ROW_RULES)} rules found something, {time.monotonic() - started:.0f}s")
        print(month)
    if months:
        try:
            refresh_reference()
        except (urllib.error.URLError, TimeoutError) as error:
            log(f"reference aggregates not refreshed ({getattr(error, 'reason', error)}); the copies in data/tlc/reference/ stand")
            return
        log("reference aggregates refreshed")


if __name__ == "__main__":
    main()
