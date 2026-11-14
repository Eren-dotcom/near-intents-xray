#!/usr/bin/env python3
"""One command that rebuilds every number and chart.

  python3 rebuild.py            rebuild from the raw data committed in this repo (about 3 minutes, offline)
  python3 rebuild.py --fetch    also refresh the public series (DefiLlama, 1Click, exact tx counts)
  python3 rebuild.py --track    also measure the last 24 hours and append a row to data/history/tracker.jsonl
  python3 rebuild.py --resample draw a NEW sample from mainnet (~40 min on the keyless endpoint);
                                moves the committed sample to data/raw/previous/ first
"""
import argparse, gzip, os, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")


def run(*a):
    print("→", " ".join(a), flush=True)
    subprocess.check_call([sys.executable, *a], cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--resample", action="store_true")
    ap.add_argument("--track", action="store_true", help="append today's row to the daily tracker (about 10 minutes, needs network)")
    a = ap.parse_args()
    gz = os.path.join(RAW, "sample_txs.jsonl.gz")
    plain = os.path.join(RAW, "sample_txs.jsonl")
    if a.resample:
        prev = os.path.join(RAW, "previous", time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(prev, exist_ok=True)
        for f in ("sample_config.json", "windows.jsonl", "sample_txs.jsonl", "sample_txs.jsonl.gz"):
            p = os.path.join(RAW, f)
            if os.path.exists(p):
                shutil.move(p, prev)
        run("scripts/sample_onchain.py")
        print("Note: the replication sample in data/raw_b is kept; it covers the previous period.")
    for d in ("raw", "raw_b", "raw_c"):      # unpack the committed samples (main, replication, third)
        g = os.path.join(ROOT, "data", d, "sample_txs.jsonl.gz")
        pl = g[:-3]
        if os.path.exists(g) and not os.path.exists(pl):
            with gzip.open(g, "rb") as i, open(pl, "wb") as o:
                shutil.copyfileobj(i, o)
    if a.fetch or a.resample:
        run("scripts/fetch_public.py")
    if a.track:
        run("scripts/track.py")
    run("scripts/analyze.py")
    run("scripts/build_report.py")
    run("tests/test_all.py")
    print("\nOpen docs/index.html (dashboard) and THESIS.md (written thesis).")


if __name__ == "__main__":
    main()
