#!/usr/bin/env python3
"""Zero-dependency checks. Run: python3 tests/test_all.py"""
import json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyze  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)


# --- unit tests of the estimator pieces ---
check("acct_type implicit", analyze.acct_type("a" * 64) == "implicit")
check("acct_type evm", analyze.acct_type("0x" + "b" * 40) == "evm")
check("acct_type named", analyze.acct_type("solver.near") == "named")
rng = random.Random(1)
num = {k: 1.0 for k in range(100)}
den = {k: 4.0 for k in range(100)}
p, lo, hi = analyze.ratio_ci(num, den, rng, list(range(100)))
check("ratio_ci exact when every window is identical", abs(p - .25) < 1e-12 and abs(lo - .25) < 1e-12 and abs(hi - .25) < 1e-12)
num = {k: (1.0 if k % 2 else 0.0) for k in range(200)}
den = {k: 1.0 for k in range(200)}
p, lo, hi = analyze.ratio_ci(num, den, rng, list(range(200)))
check("ratio_ci interval brackets the point and has binomial width", lo < p < hi and 0.10 < hi - lo < 0.18, f"{lo} {p} {hi}")
check("corr of a line is 1", abs(analyze.corr([1, 2, 3, 4], [2, 4, 6, 8]) - 1) < 1e-12)
check("corr handles constants", analyze.corr([1, 1, 1], [1, 2, 3]) is None)

# --- reproducibility of the sampling plan ---
for sample_dir in ("raw", "raw_b", "raw_c"):
  cfg_p = os.path.join(ROOT, "data", sample_dir, "sample_config.json")
  win_p = os.path.join(ROOT, "data", sample_dir, "windows.jsonl")
  if os.path.exists(cfg_p) and os.path.exists(win_p):
      cfg = json.load(open(cfg_p))
      r = random.Random(cfg["seed"])
      plan = {}
      for k in range(cfg["n_strata"]):
          s_hi = cfg["end_height"] - k * cfg["stratum_blocks"]
          lo_ = r.randint(s_hi - cfg["stratum_blocks"] + 1, s_hi - cfg["window_blocks"] + 1)
          plan[k] = (lo_, lo_ + cfg["window_blocks"] - 1)
      wins = [json.loads(l) for l in open(win_p)]
      check(f"{sample_dir}: committed windows equal the seeded plan", all(plan[w["k"]] == (w["lo"], w["hi"]) for w in wins))
      check(f"{sample_dir}: one window per stratum, inside its stratum", all(
          cfg["end_height"] - w["k"] * cfg["stratum_blocks"] - cfg["stratum_blocks"] < w["lo"] and
          w["hi"] <= cfg["end_height"] - w["k"] * cfg["stratum_blocks"] for w in wins))

# --- sanity of the derived numbers ---
np_ = os.path.join(ROOT, "data", "derived", "numbers.json")
if os.path.exists(np_):
    N = json.load(open(np_))
    g = N["generated_from"]
    check("price coverage of token legs >= 95%", g["price_coverage"] >= 0.95, str(g["price_coverage"]))
    check("windows used > 0", g["windows_used"] > 0)
    for name, row in (("receiver", N["ledger"]["receivers"]), ("sender", N["ledger"]["senders"])):
        tot = sum(x["share"][0] for x in row)
        check(f"top {name} shares sum to <= 100%", tot <= 1.0000001, str(tot))
    for side in ("deposits", "withdrawals"):
        tot = sum(x["share"][0] for x in N["chains"][side])
        check(f"{side} chain shares sum to <= 100%", tot <= 1.0000001, str(tot))
    for path in (N["assets"]["stable_share"], N["access"]["top5_signer_share"], N["ledger"]["top1_sender_share"]):
        check("interval ordered lo <= point <= hi", path[1] <= path[0] <= path[2], str(path))
    rob = N.get("robustness", [])
    if rob:
        check("robustness: main run present", rob[0]["name"] == "Main sample")
        for r in rob[1:]:
            if r["name"] in ("Replication sample", "Prices at fetch time"):
                for t in ("T3", "T4", "T5"):
                    a_, b_ = rob[0][t], r[t]
                    check(f"robustness: {t} intervals of main and '{r['name']}' overlap",
                          a_[1] <= b_[2] and b_[1] <= a_[2], f"{a_} vs {b_}")
    rc = N["reconciliation"]
    if "sample_tx_over_exact_tx" in rc:
        check("sample tx count within 15% of the exact count", 0.85 <= rc["sample_tx_over_exact_tx"] <= 1.15,
              str(rc["sample_tx_over_exact_tx"]))
    cf = N.get("confidential")
    if cf:
        check("treasury account is the one named in NEAR's docs",
              cf["treasury"] == "51e8f94d77b5e90dc9852ca6113771e11e8382ce69473a75e313e41665de7cbe")
        for k in ("shield_share_of_transfers", "unshield_share_of_transfers", "shield_vs_public_swaps"):
            v = cf[k]
            check(f"confidential: {k} is a share with an ordered interval", 0 <= v[1] <= v[0] <= v[2] <= 1, str(v))
        check("confidential: shield share cannot exceed the treasury's either-side share",
              cf["shield_share_of_transfers"][0] <= N["ledger"]["top1_either_side"]["share"][0] + 1e-9)
    th = os.path.join(ROOT, "THESIS.md")
    if os.path.exists(th):
        check("THESIS.md has no unfilled placeholders", "{{" not in open(th).read())
    ix = os.path.join(ROOT, "docs", "index.html")
    if os.path.exists(ix):
        t = open(ix).read()
        import re
        js = " ".join(re.findall(r"<script>(.*?)</script>", t, re.S))   # URLs in prose are citations, not requests
        hosts = set(re.findall(r"https?://([a-z0-9.-]+)", js))
        check("no clickable or embedded external resource outside the scripts", "href=\"http" not in t and "url(http" not in t)
        check("dashboard loads no external scripts, styles, fonts or images", "src=\"http" not in t and "<link" not in t and "@import" not in t)
        check("the only hosts the dashboard can call are DefiLlama's (the labelled live strip)",
              hosts <= {"api.llama.fi", "coins.llama.fi"}, str(hosts))
    sw = N.get("switch")
    if sw:
        check("switch: periods do not overlap and both have at least 5 days",
              sw["before"]["to"] < sw["after"]["from"] == sw["first_day_after"] and min(sw["before"]["days"], sw["after"]["days"]) >= 5)
        check("switch: daily rows carry the series the chart uses", all("swap_tx_share" in r and "public_swap_usd" in r for r in N["daily"]))
    if sw and sw.get("break_date_bootstrap"):
        bb = sw["break_date_bootstrap"]
        check("switch: bootstrap range contains the point estimate and shares sum to 1",
              bb["range_95"][0] <= sw["first_day_after"] <= bb["range_95"][1] and abs(sum(x[1] for x in bb["distribution"]) - 1) < 1e-6)
    shd = N["confidential"].get("shielders")
    if shd:
        check("shielders: top-10 share is at least the top account's share and at most 1",
              shd["top"][0]["share"][0] <= shd["top10_share"][0] <= 1)
    dd = os.path.join(ROOT, "docs", "data", "daily.csv")
    if os.path.exists(dd):
        check("CSV export: daily.csv has one row per day in numbers.json", sum(1 for _ in open(dd)) - 1 == len(N["daily"]))
    pe = os.path.join(ROOT, "data", "public", "peers.json")
    if os.path.exists(pe):
        rows = json.load(open(pe))["rows"]
        check("peers: NEAR Intents is in the list and no take rate is computed without a volume",
              any(r["slug"] == "near-intents" for r in rows) and all(r.get("volume_30d") or "take" not in r for r in rows))
    if N.get("timing"):
        check("timing: hourly and weekday shares each sum to 1",
              abs(sum(N["timing"]["by_utc_hour"]) - 1) < 1e-9 and abs(sum(N["timing"]["by_weekday_mon0"]) - 1) < 1e-9)
    pp = os.path.join(ROOT, "predictions.json")
    if os.path.exists(pp):
        P = json.load(open(pp))
        check("predictions: registered before the horizon, 5 entries, known rules",
              P["registered"] < P["horizon"] and len(P["predictions"]) == 5 and all(p["rule"] in ("at_least", "above", "below") for p in P["predictions"]))
        if os.path.exists(os.path.join(ROOT, "data", "history", "tracker.jsonl")):
            r0 = json.loads(open(os.path.join(ROOT, "data", "history", "tracker.jsonl")).readline())
            check("predictions: every metric exists in tracker rows", all(p["metric"] in r0 for p in P["predictions"]))
    tb = os.path.join(ROOT, "data", "public", "treasury_balance.json")
    if os.path.exists(tb):
        B = json.load(open(tb))
        check("treasury balance: rows add up to the total and the account is the documented treasury",
              abs(sum(r["usd"] for r in B["rows"]) - B["total_usd"]) < 1 and B["account"] == N["confidential"]["treasury"])
    rp = os.path.join(ROOT, "docs", "report.html")
    if os.path.exists(rp):
        rt = open(rp).read()
        check("research note: at least 14 exhibits, no unfilled placeholders, no external resources",
              rt.count("<b>Exhibit ") >= 14 and "{_" not in rt and "None" not in re.sub(r"<[^>]+>", "", rt) and "src=\"http" not in rt and "<link" not in rt)
    lp = os.path.join(ROOT, "data", "public", "intents_tx_counts_long.json")
    sp = os.path.join(ROOT, "data", "public", "intents_tx_counts.json")
    if os.path.exists(lp) and os.path.exists(sp):
        Lg = {r[0]: r[1] for r in json.load(open(lp))["rows"]}
        Sh = {r[0]: r[1] for r in json.load(open(sp))["rows"]}
        both = [d for d in Sh if d in Lg and Sh[d]]
        check("180-day exact counts agree with the 45-day file on every shared day (within 1%)",
              len(both) >= 30 and all(abs(Lg[d] - Sh[d]) <= 0.01 * Sh[d] for d in both))
    mc = N["confidential"].get("memo_check")
    if mc:
        check("memo check: every shield transfer has a long memo and counts add up",
              mc["shield_with_long_memo"] == mc["shield_transfers"] > 0 and mc["other_with_long_memo"] <= mc["other_transfers"])
    hp = os.path.join(ROOT, "data", "history", "tracker.jsonl")
    if os.path.exists(hp):
        rows = [json.loads(l) for l in open(hp) if l.strip()]
        check("tracker: one row per date, in order", [r["date"] for r in rows] == sorted({r["date"] for r in rows}))
        for r in rows:
            check(f"tracker {r['date']}: seed is the date and shares are valid",
                  r["seed"] == int(r["date"].replace("-", "")) and all(0 <= r[k][1] <= r[k][0] <= r[k][2] <= 1 for k in ("T3", "T4", "T5")))

print()
if fails:
    sys.exit(f"{len(fails)} check(s) failed: {fails}")
print("all checks passed")
