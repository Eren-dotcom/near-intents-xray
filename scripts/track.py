#!/usr/bin/env python3
"""Daily tracker: re-measure the last 24 hours and append one row to data/history/tracker.jsonl.

This does NOT touch the committed 30-day snapshot (data/raw, data/raw_b, data/public) or its verdicts.
It draws a small fresh sample (96 strata of 1,500 blocks = about 24 hours, one 40-block window each,
seed = the UTC date as YYYYMMDD), values it with a freshly fetched 1Click price list, and records the
same figures the six tests use, so the dashboard can show whether they move after the snapshot.
About 6-10 minutes on the keyless FastNEAR endpoint. Set FASTNEAR_API_KEY to go faster.

Usage: python3 scripts/track.py [--strata 96] [--keep]
"""
import argparse, datetime as dt, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
HIST = os.path.join(ROOT, "data", "history")
TMP, TPUB = "track_tmp", os.path.join(ROOT, "data", "track_pub")


def bps30(L):
    """NEAR's revenue over published volume, last 30 COMPLETE days, in basis points."""
    v = {t: x for t, x in L["volume"][:-1]}
    r = {t: x for t, x in L["revenue"][:-1]}
    days = sorted(v)[-30:]
    tv = sum(v[t] for t in days)
    return sum(r.get(t, 0) for t in days) / tv * 1e4 if tv else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strata", type=int, default=96)
    ap.add_argument("--keep", action="store_true", help="keep the temporary sample (for debugging)")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted download")
    a = ap.parse_args()
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    seed = int(today.replace("-", ""))
    raw = os.path.join(ROOT, "data", TMP)
    if not a.resume:
        shutil.rmtree(raw, ignore_errors=True)
    os.makedirs(TPUB, exist_ok=True)
    os.makedirs(HIST, exist_ok=True)

    import fetch_public
    fetch_public.PUB = TPUB
    fetch_public.llama()
    fetch_public.tokens()

    subprocess.check_call([sys.executable, os.path.join(HERE, "sample_onchain.py"), "--dir", TMP, "--seed", str(seed),
                           "--strata", str(a.strata), "--stratum-blocks", "1500", "--window", "40"])
    import analyze
    analyze.PUB = TPUB
    o = analyze.run(raw=TMP, price_mode="spot", boot=1000, write=False)
    k = analyze.key_metrics(o)
    cfg = json.load(open(os.path.join(raw, "sample_config.json")))
    L = json.load(open(os.path.join(TPUB, "defillama.json")))
    last = lambda s: L[s][-2] if len(L[s]) > 1 else L[s][-1]   # last COMPLETE day (the final row is today, partial)
    vol, rev = last("volume"), last("revenue")
    cf = o["confidential"]
    dep = o["totals_per_day"]["deposit_usd"]
    row = {"date": today, "measured_at": int(time.time()), "seed": seed, "end_height": cfg["end_height"],
           "strata": cfg["n_strata"], "stratum_blocks": cfg["stratum_blocks"], "window_blocks": cfg["window_blocks"],
           "windows": k["windows"], "transactions": k["transactions"],
           "T2": k["T2"], "T2_chain": k["T2_chain"], "T3": k["T3"], "T4": k["T4"], "T5": k["T5"],
           "treasury_either_side": k["router"], "shield_vs_public": k["shield_vs_public"],
           "shield_usd_per_day": cf["shield_usd_per_day"], "public_swap_usd_per_day": cf["public_swap_usd_per_day"],
           "deposit_usd_per_day": dep, "transactions_per_day": o["totals_per_day"]["transactions"],
           "published_volume_last_full_day": vol[1], "published_day": dt.datetime.fromtimestamp(vol[0], dt.timezone.utc).strftime("%Y-%m-%d"),
           "T6_bps_last_full_day": (rev[1] / vol[1] * 1e4) if vol[1] else None,
           "T6_bps_30d": bps30(L)}
    p = os.path.join(HIST, "tracker.jsonl")
    rows = [json.loads(l) for l in open(p)] if os.path.exists(p) else []
    rows = [r for r in rows if r["date"] != today] + [row]
    rows.sort(key=lambda r: r["date"])
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    print("tracker row for", today, json.dumps(row)[:400])
    if not a.keep:
        shutil.rmtree(raw, ignore_errors=True)
        shutil.rmtree(TPUB, ignore_errors=True)


if __name__ == "__main__":
    main()
