"""Fetch the three Ken French daily factor files used by the paper into data/factors/.

The files are not committed (third-party data); this script downloads the current library versions
and reports their SHA-256 so a reader can compare with the vintage the paper used
(data/checksums/manifest.csv records the 202606 CRSP vintage). Run: ``python data/fetch_ken_french.py``.
"""
from __future__ import annotations
import hashlib, io, sys, urllib.request, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {"F-F_Research_Data_5_Factors_2x3_daily_CSV.zip": "F-F_Research_Data_5_Factors_2x3_daily.csv",
         "F-F_Momentum_Factor_daily_CSV.zip": "F-F_Momentum_Factor_daily.csv",
         "F-F_ST_Reversal_Factor_daily_CSV.zip": "F-F_ST_Reversal_Factor_daily.csv"}


def main() -> None:
    paths.FACTORS.mkdir(parents=True, exist_ok=True)
    for zname, csv in FILES.items():
        blob = urllib.request.urlopen(BASE + zname, timeout=60).read()
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            data = z.read(csv)
        (paths.FACTORS / csv).write_bytes(data)
        print(f"{csv}: {len(data):,} bytes  sha256 {hashlib.sha256(data).hexdigest()[:16]}…")


if __name__ == "__main__":
    main()
