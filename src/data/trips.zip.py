"""Bundle the committed monthly trip summaries into the archive the page reads.

Observable Framework runs this at build time and serves its stdout as
data/trips.zip; the page pulls daily.parquet, hourly.parquet, zones.parquet and
meta.json out of it. No network: scripts/fetch_tlc.py is what talks to TLC, and
its output lives in data/tlc/YYYY-MM/.
"""

import io
import json
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb

DATA = Path(__file__).resolve().parents[2] / "data" / "tlc"
MONTH = re.compile(r"\d{4}-\d{2}")


def main():
    # Finished months only: fetch_tlc.py builds a month in a dot-prefixed directory first.
    months = sorted(p.name for p in DATA.iterdir() if p.is_dir() and MONTH.fullmatch(p.name) and (p / "daily.parquet").exists())
    if not months:
        raise SystemExit(f"no monthly summaries in {DATA}; run scripts/fetch_tlc.py")

    con = duckdb.connect()
    archive = io.BytesIO()
    rows = {}
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as zf:
        for name in ("daily", "hourly", "zones"):
            files = [str(DATA / m / f"{name}.parquet") for m in months]
            path = Path(tmp) / f"{name}.parquet"
            con.execute(f"COPY (SELECT * FROM read_parquet({files!r})) TO '{path}' (FORMAT parquet, COMPRESSION zstd)")
            rows[name] = con.execute(f"SELECT count(*) FROM read_parquet({files!r})").fetchone()[0]
            zf.write(path, path.name)
        meta = {
            "source": "NYC Taxi & Limousine Commission, High Volume For-Hire Vehicle trip records",
            "source_page": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
            "months": months,
            "rows": rows,
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        zf.writestr("meta.json", json.dumps(meta, indent=2))
    sys.stdout.buffer.write(archive.getvalue())


if __name__ == "__main__":
    main()
