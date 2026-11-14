#!/usr/bin/env python3
"""Stratified random sample of intents.near transactions (keyless, FastNEAR transactions API).

Design
  * The last N_STRATA * STRATUM blocks before a fixed end height are cut into strata of STRATUM
    blocks (default 6,000 blocks ~ 1 hour; 720 strata ~ 30 days).
  * In every stratum one window of WINDOW consecutive blocks is drawn with a seeded RNG.
  * EVERY transaction touching intents.near inside the window is downloaded with all receipts,
    and the intents.near event logs are kept.
  * Each window stands for STRATUM / WINDOW windows: an unbiased expansion estimator.

The config (end height, seed, sizes) is written once to data/raw/sample_config.json, so a re-run
re-draws exactly the same windows. Both phases are resumable.

The public endpoint allows roughly 60 requests a minute, so the default run takes ~40 minutes.
Set FASTNEAR_API_KEY (free at fastnear.com) and lower --gap to go faster.

Usage: python3 scripts/sample_onchain.py [--strata 720] [--stratum-blocks 6000] [--window 40]
"""
import argparse, json, os, random, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
CFG = os.path.join(RAW, "sample_config.json")
WIN = os.path.join(RAW, "windows.jsonl")
OUT = os.path.join(RAW, "sample_txs.jsonl")
API = "https://tx.main.fastnear.com/v0"
KEY = os.environ.get("FASTNEAR_API_KEY")
CONTRACT = "intents.near"
GAP = 1.15
_last = [0.0]


def post(path, body):
    """Rate-limited POST. A 429 is waited out, never skipped, so no transaction is silently lost."""
    url = API + path + (("?apiKey=" + KEY) if KEY else "")
    fails = 0
    while True:
        wait = GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "near-intents-xray"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20)
                continue
            fails += 1
        except Exception:
            fails += 1
        if fails >= 5:
            return None
        time.sleep(2 * fails)


def slim(data):
    """Drop bulky fields the analysis never reads (nonces, long opaque memos keep only a length)."""
    if isinstance(data, list):
        return [slim(x) for x in data]
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if k == "nonce":
                continue
            if k == "memo" and isinstance(v, str) and len(v) > 40:
                out[k] = "<%d chars>" % len(v)
                continue
            out[k] = slim(v)
        return out
    return data


def list_window(lo, hi):
    """All tx hashes touching the contract with lo <= height <= hi (paginates past 200)."""
    seen, top = {}, hi
    while top >= lo:
        d = post("/account", {"account_id": CONTRACT, "from_tx_block_height": lo,
                              "to_tx_block_height": top, "limit": 200})
        if d is None:
            raise RuntimeError("listing failed")
        rows = d.get("account_txs") or []
        for r in rows:
            seen[r["transaction_hash"]] = r["tx_block_height"]
        if len(rows) < 200:
            break
        low = min(r["tx_block_height"] for r in rows)
        top = low if low < top else top - 1
    return seen


def parse_tx(t):
    tx = t["transaction"]
    ev = []
    for rc in t.get("receipts", []):
        o = rc["execution_outcome"]["outcome"]
        if o.get("executor_id") != CONTRACT:
            continue
        for l in o.get("logs", []):
            if l.startswith("EVENT_JSON:"):
                try:
                    e = json.loads(l[11:])
                except Exception:
                    continue
                ev.append([e.get("standard"), e.get("event"), slim(e.get("data"))])
    eo = t["execution_outcome"]
    return {"tx": tx["hash"], "h": eo["block_height"], "t": eo["block_timestamp"] // 10**9,
            "signer": tx["signer_id"], "recv": tx["receiver_id"], "ev": ev}


def main():
    global GAP
    ap = argparse.ArgumentParser()
    ap.add_argument("--strata", type=int, default=720)
    ap.add_argument("--stratum-blocks", type=int, default=6000)
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261114)
    ap.add_argument("--gap", type=float, default=GAP, help="seconds between requests")
    ap.add_argument("--dir", default="raw", help="sub-directory of data/ to write to (e.g. raw_b for a replication)")
    ap.add_argument("--end-height", type=int, help="reuse the end height of another sample to cover the same period")
    a = ap.parse_args()
    GAP = a.gap
    global RAW, CFG, WIN, OUT
    RAW = os.path.join(ROOT, "data", a.dir)
    CFG, WIN, OUT = (os.path.join(RAW, f) for f in ("sample_config.json", "windows.jsonl", "sample_txs.jsonl"))
    os.makedirs(RAW, exist_ok=True)
    if os.path.exists(CFG):
        cfg = json.load(open(CFG))
    else:
        if a.end_height:
            end = a.end_height
        else:
            d = post("/account", {"account_id": CONTRACT, "limit": 1})
            end = d["account_txs"][0]["tx_block_height"] - 600   # stay ~6 minutes behind the tip
        cfg = {"contract": CONTRACT, "api": API, "end_height": end,
               "stratum_blocks": a.stratum_blocks, "n_strata": a.strata,
               "window_blocks": a.window, "seed": a.seed}
        json.dump(cfg, open(CFG, "w"), indent=1)
    rng = random.Random(cfg["seed"])
    S, W = cfg["stratum_blocks"], cfg["window_blocks"]
    plan = []
    for k in range(cfg["n_strata"]):
        s_hi = cfg["end_height"] - k * S
        lo = rng.randint(s_hi - S + 1, s_hi - W + 1)
        plan.append((k, lo, lo + W - 1))

    # phase 1: list every window
    wins = {}
    if os.path.exists(WIN):
        for line in open(WIN):
            r = json.loads(line)
            wins[r["k"]] = r
    with open(WIN, "a") as f:
        for k, lo, hi in plan:
            if k in wins:
                continue
            seen = list_window(lo, hi)
            r = {"k": k, "lo": lo, "hi": hi, "txs": sorted(seen, key=lambda x: seen[x])}
            wins[k] = r
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
            f.flush()
            if k % 50 == 0:
                print(f"listed window {k}/{len(plan)}", flush=True)

    # phase 2: download every listed transaction, 20 per request
    have = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            have.add(json.loads(line)["tx"])
    owner = {}
    for k, r in wins.items():
        for h in r["txs"]:
            owner.setdefault(h, k)
    todo = [h for h in owner if h not in have]
    print(f"{len(owner)} txs listed, {len(have)} already saved, {len(todo)} to fetch", flush=True)
    with open(OUT, "a") as f:
        for i in range(0, len(todo), 20):
            batch = todo[i:i + 20]
            d = post("/transactions", {"tx_hashes": batch})
            txs = d.get("transactions", []) if d else []
            if d is None:
                for h in batch:
                    d1 = post("/transactions", {"tx_hashes": [h]})
                    txs += d1.get("transactions", []) if d1 else []
            for t in txs:
                rec = parse_tx(t)
                rec["k"] = owner.get(rec["tx"])
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            f.flush()
            if (i // 20) % 50 == 0:
                print(f"fetched {i}/{len(todo)}", flush=True)
    print("finished", flush=True)


if __name__ == "__main__":
    main()
