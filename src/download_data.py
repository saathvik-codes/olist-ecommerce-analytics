"""Download the Olist CSVs from the public GitHub mirror and verify row counts."""
import sys
import urllib.request

import duckdb

from config import RAW_DIR, RAW_FILES, SOURCE_BASE_URL


def download() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in RAW_FILES:
        target = RAW_DIR / name
        if target.exists() and target.stat().st_size > 0:
            continue
        print(f"  downloading {name}")
        urllib.request.urlretrieve(f"{SOURCE_BASE_URL}/{name}", target)


def verify() -> bool:
    ok = True
    con = duckdb.connect()
    print(f"  {'file':<42}{'rows':>10}{'expected':>10}")
    for name, expected in RAW_FILES.items():
        path = (RAW_DIR / name).as_posix()
        rows = con.execute(
            "SELECT count(*) FROM read_csv(?, header = true)", [path]
        ).fetchone()[0]
        flag = "" if rows == expected else "  <-- MISMATCH"
        ok &= rows == expected
        print(f"  {name:<42}{rows:>10,}{expected:>10,}{flag}")
    return ok


if __name__ == "__main__":
    download()
    sys.exit(0 if verify() else 1)
