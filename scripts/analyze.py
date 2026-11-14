#!/usr/bin/env python3
"""Turn the raw sample + public series into data/derived/numbers.json (everything the dashboard
and THESIS.md print). Pure standard library, deterministic (fixed bootstrap seed).

Estimator. Windows are drawn one per stratum, each stratum S blocks and each window W blocks, so a
sample total times S/W estimates the population total. Shares are ratios of two such totals; their
95% intervals come from a bootstrap that resamples whole windows (2,000 draws), which respects the
clustering of transactions inside a window.
"""
import time
import bisect, collections, datetime as dt, json, math, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
PUB = os.path.join(ROOT, "data", "public")
DER = os.path.join(ROOT, "data", "derived")
STABLES = {"USDT", "USDC", "DAI", "USD1", "USDE", "FRAX", "PYUSD", "USDS", "TUSD", "USDD",
           "USDT0", "FDUSD", "USDF", "XDAI", "EURE", "GNOEURE", "USDC.E", "RLUSD", "USDG"}
BOOT = 2000
# Accounts whose role is documented by NEAR. Source for the treasury: the NEAR Intents docs list it as
# PRIVATE_TREASURY_ACCOUNT_ID, "Treasury account for asset wrapping", a production constant, and
# describe a transfer into it as the "shield" step of a confidential swap.
TREASURY = "51e8f94d77b5e90dc9852ca6113771e11e8382ce69473a75e313e41665de7cbe"
KNOWN = {TREASURY: {"label": "Confidential Intents Treasury",
                    "source": "https://docs.near-intents.org/integration/market-makers/confidential-example"}}


def acct_type(a):
    if a is None:
        return "unknown"
    if len(a) == 64 and all(c in "0123456789abcdef" for c in a):
        return "implicit"
    if a.startswith("0x") and len(a) == 42:
        return "evm"
    return "named"


def load_tokens():
    toks = json.load(open(os.path.join(PUB, "tokens_1click.json")))["tokens"]
    out = {}
    for t in toks:
        out[t["assetId"]] = t
        # mt events of HOT omni tokens sometimes carry only the inner id
        if t["assetId"].startswith("nep245:"):
            out[t["assetId"].split(":", 2)[2]] = t
    return out


class Pricer:
    """mode 'day': value each leg at the asset's USD price on the day of the transaction (DefiLlama
    daily series); fall back to the 1Click list price when no daily price exists.
    mode 'spot': always use the 1Click list price at fetch time."""

    def __init__(self, mode="day"):
        self.tok = load_tokens()
        self.hit = self.miss = self.at_day = 0
        self.missing = collections.Counter()
        self.daily = {}
        pp = os.path.join(PUB, "prices_daily.json")
        if mode == "day" and os.path.exists(pp):
            self.daily = json.load(open(pp))["prices"]

    def value(self, token_id, amount, date=None):
        """-> (usd, chain, symbol) or None when the asset is not in the 1Click list."""
        t = self.tok.get(token_id)
        if t is None or not t.get("price"):
            self.miss += 1
            self.missing[token_id] += 1
            return None
        self.hit += 1
        price = t["price"]
        series = self.daily.get(t.get("coingeckoId") or "")
        if series and date in series:
            price = series[date]
            self.at_day += 1
        usd = abs(int(amount)) / 10 ** t["decimals"] * price
        return usd, t["blockchain"], t["symbol"].upper()


def items(d):
    return d if isinstance(d, list) else [d]


def load_sample():
    cfg_p = os.path.join(RAW, "sample_config.json")
    cfg = json.load(open(cfg_p)) if os.path.exists(cfg_p) else None
    txs, seen = [], set()
    with open(os.path.join(RAW, "sample_txs.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            if "tx" not in r or r["tx"] in seen:
                continue
            seen.add(r["tx"])
            txs.append(r)
    wins = {}
    wp = os.path.join(RAW, "windows.jsonl")
    if os.path.exists(wp):
        for line in open(wp):
            r = json.loads(line)
            wins[r["k"]] = r
    return cfg, txs, wins


def ratio_ci(num, den, rng, ks):
    """num, den: dict window -> value. Returns (point, lo, hi) with a window bootstrap."""
    N, D = sum(num.get(k, 0) for k in ks), sum(den.get(k, 0) for k in ks)
    point = N / D if D else float("nan")
    pairs = [(num.get(k, 0.0), den.get(k, 0.0)) for k in ks]
    n = len(pairs)
    vals = []
    for _ in range(BOOT):
        a = b = 0.0
        for _ in range(n):
            x, y = pairs[rng.randrange(n)]
            a += x
            b += y
        if b:
            vals.append(a / b)
    vals.sort()
    if not vals:
        return [point, None, None]
    return [point, vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]]


def total_ci(val, rng, ks, scale):
    xs = [val.get(k, 0.0) for k in ks]
    n = len(xs)
    point = sum(xs) * scale
    vals = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) * scale for _ in range(BOOT))
    return [point, vals[int(0.025 * BOOT)], vals[int(0.975 * BOOT)]]


def day(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")


def run(raw="raw", half=None, cap=None, price_mode="day", boot=2000, write=True):
    """raw: sub-directory of data/ holding a sample. half: 'recent' or 'older' keeps one half of
    the strata. cap: drop every single item worth >= cap USD (whale sensitivity)."""
    global RAW, BOOT
    RAW, BOOT = os.path.join(ROOT, "data", raw), boot
    os.makedirs(DER, exist_ok=True)
    cfg, txs, wins = load_sample()
    if not txs:
        sys.exit("no sample: run scripts/sample_onchain.py first")
    pr = Pricer(price_mode)
    rng = random.Random(7)
    S = cfg["stratum_blocks"] if cfg else 6000
    W = cfg["window_blocks"] if cfg else 200
    complete = None
    if wins:   # only windows whose every listed tx was downloaded are used
        got = collections.Counter(t["k"] for t in txs)
        complete = sorted(k for k, w in wins.items() if got.get(k, 0) >= len(w["txs"]))
    ks = complete if complete is not None else sorted({t["k"] for t in txs})
    if half and cfg:
        mid = cfg["n_strata"] // 2
        ks = [k for k in ks if (k < mid) == (half == "recent")]
    kset = set(ks)
    txs = [t for t in txs if t["k"] in kset]
    scale = S / W

    # window -> approximate unix time (windows with zero txs still need a date)
    pts = sorted((t["h"], t["t"]) for t in txs)
    hs = [p[0] for p in pts]

    def time_of(h):
        i = min(max(bisect.bisect_left(hs, h), 1), len(pts) - 1)
        (h0, t0), (h1, t1) = pts[i - 1], pts[i]
        return t0 if h1 == h0 else t0 + (h - h0) * (t1 - t0) / (h1 - h0)

    win_day = {}
    for k in ks:
        if wins:
            win_day[k] = day(time_of(wins[k]["lo"]))
    if not wins:
        for t in txs:
            win_day[t["k"]] = day(t["t"])

    Z = lambda: collections.defaultdict(float)
    w_tx, w_transfer_usd, w_dep, w_wd, w_diff = Z(), Z(), Z(), Z(), Z()
    w_stable, w_self, w_big = Z(), Z(), Z()
    w_recv = collections.defaultdict(Z)     # account -> window -> usd received via transfer
    w_sent = collections.defaultdict(Z)
    w_dep_chain = collections.defaultdict(Z)
    w_diff_acct = collections.defaultdict(Z)   # account -> window -> usd received via token_diff
    w_ref = collections.defaultdict(Z)         # referral tag -> window -> usd
    w_either = collections.defaultdict(Z)      # account -> window -> usd of transfers it is a party to
    w_wd_chain = collections.defaultdict(Z)
    w_asset = collections.defaultdict(Z)
    w_signer = collections.defaultdict(Z)
    w_srctype = collections.defaultdict(Z)
    w_shield, w_unshield, w_shield_n, w_shield_memo = Z(), Z(), Z(), Z()
    w_shield_acct = {}
    w_shield_src = collections.defaultdict(Z)
    acct_windows = collections.defaultdict(set)
    acct_cp = collections.defaultdict(set)
    ev_count = collections.Counter()
    sizes = []
    referral = collections.Counter()
    n_transfers = n_memo = 0

    for t in txs:
        k = t["k"]
        dy = day(t["t"])
        w_tx[k] += 1
        w_signer[t["signer"]][k] += 1
        if t["signer"] not in ("intents.near",) and acct_type(t["signer"]) != "named":
            w_self[k] += 1
        for std, name, data in t["ev"]:
            ev_count[f"{std}:{name}"] += 1
            if std == "dip4" and name == "transfer":
                for it in items(data):
                    legs = [v for v in (pr.value(tid, amt, dy) for tid, amt in
                                        (it.get("tokens") or {}).items()) if v]
                    usd = sum(v[0] for v in legs)
                    if cap and usd >= cap:
                        continue
                    for v in legs:
                        w_asset[v[2]][k] += v[0]
                        if v[2] in STABLES:
                            w_stable[k] += v[0]
                    a, b = it.get("account_id"), it.get("receiver_id")
                    n_transfers += 1
                    if str(it.get("memo", "")).startswith("<"):
                        n_memo += 1
                    w_transfer_usd[k] += usd
                    w_sent[a][k] += usd
                    w_recv[b][k] += usd
                    w_either[a][k] += usd
                    if b != a:
                        w_either[b][k] += usd
                    w_srctype[acct_type(a)][k] += usd
                    if b == TREASURY and a != TREASURY:
                        w_shield[k] += usd
                        w_shield_n[k] += 1
                        w_shield_src[acct_type(a)][k] += usd
                        w_shield_acct.setdefault(a, collections.Counter())[k] += usd
                        if str(it.get("memo", "")).startswith("<"):
                            w_shield_memo[k] += 1
                    elif a == TREASURY:
                        w_unshield[k] += usd
                    acct_windows[a].add(k)
                    acct_windows[b].add(k)
                    acct_cp[a].add(b)
                    acct_cp[b].add(a)
                    sizes.append(usd)
                    if usd >= 100_000:
                        w_big[k] += usd
            elif std == "dip4" and name == "token_diff":
                for it in items(data):
                    pos = 0.0
                    for tid, amt in (it.get("diff") or {}).items():
                        if not str(amt).startswith("-"):
                            v = pr.value(tid, amt, dy)
                            if v:
                                pos += v[0]
                    if cap and pos >= cap:
                        continue
                    w_diff[k] += pos
                    w_diff_acct[it.get("account_id")][k] += pos
                    acct_windows[it.get("account_id")].add(k)
                    if it.get("referral"):
                        referral[it["referral"]] += 1
                        w_ref[it["referral"]][k] += pos
            elif std == "nep245" and name in ("mt_mint", "mt_burn"):
                for it in items(data):
                    for tid, amt in zip(it.get("token_ids") or [], it.get("amounts") or []):
                        v = pr.value(tid, amt, dy)
                        if not v or (cap and v[0] >= cap):
                            continue
                        if name == "mt_mint":
                            w_dep[k] += v[0]
                            w_dep_chain[v[1]][k] += v[0]
                        else:
                            w_wd[k] += v[0]
                            w_wd_chain[v[1]][k] += v[0]

    nwin = len(ks)
    span_days = nwin * S * 0.6 / 86400 if not pts else (max(p[1] for p in pts) - min(p[1] for p in pts)) / 86400
    span_days = max(span_days, 1e-9)
    days = sorted(set(win_day.values()))

    def per_day(val):
        p, lo, hi = total_ci(val, rng, ks, scale)
        return [p / span_days, lo / span_days, hi / span_days]

    def top_shares(by_acct, den, n=12):
        tot = {a: sum(v.values()) for a, v in by_acct.items()}
        order = sorted(tot, key=tot.get, reverse=True)
        rows = []
        for a in order[:n]:
            rows.append({"account": a, "type": acct_type(a), "usd_sample": tot[a],
                         "share": ratio_ci(by_acct[a], den, rng, ks),
                         "windows": len(acct_windows[a]), "window_share": len(acct_windows[a]) / nwin,
                         "counterparties": len(acct_cp[a])})
        return order, tot, rows

    T = sum(w_transfer_usd.values())
    r_order, r_tot, r_rows = top_shares(w_recv, w_transfer_usd)
    s_order, s_tot, s_rows = top_shares(w_sent, w_transfer_usd)

    def cum_share(order, by, n):
        num = Z()
        for a in order[:n]:
            for k, v in by[a].items():
                num[k] += v
        return ratio_ci(num, w_transfer_usd, rng, ks)

    def hhi(tot):
        s = sum(tot.values())
        return sum((v / s) ** 2 for v in tot.values()) * 10000 if s else None

    # standing accounts: seen in >= 5% of windows. Everything else is a transient account.
    thresh = max(2, math.ceil(0.05 * nwin))
    standing = {a for a, w in acct_windows.items() if len(w) >= thresh}
    num_touch, num_both = Z(), Z()
    for t in txs:
        dy = day(t["t"])
        for std, name, data in t["ev"]:
            if std == "dip4" and name == "transfer":
                for it in items(data):
                    usd = sum((pr.value(tid, amt, dy) or (0,))[0] for tid, amt in (it.get("tokens") or {}).items())
                    if cap and usd >= cap:
                        continue
                    a, b = it.get("account_id") in standing, it.get("receiver_id") in standing
                    if a or b:
                        num_touch[t["k"]] += usd
                    if a and b:
                        num_both[t["k"]] += usd
    legs_total, legs_miss, legs_day = pr.hit // 2, pr.miss // 2, pr.at_day // 2   # each transfer leg is priced twice
    stand_rows = []
    for a in sorted(standing, key=lambda x: -(r_tot.get(x, 0) + s_tot.get(x, 0)))[:15]:
        stand_rows.append({"account": a, "type": acct_type(a), "received": r_tot.get(a, 0.0),
                           "sent": s_tot.get(a, 0.0), "window_share": len(acct_windows[a]) / nwin,
                           "counterparties": len(acct_cp[a])})

    e_tot = {a: sum(v.values()) for a, v in w_either.items()}
    e_top = max(e_tot, key=e_tot.get)
    either = {"account": e_top, "share": ratio_ci(w_either[e_top], w_transfer_usd, rng, ks)}
    d_tot = {a: sum(v.values()) for a, v in w_diff_acct.items()}
    diff_rows = [{"account": a, "type": acct_type(a), "share": ratio_ci(w_diff_acct[a], w_diff, rng, ks),
                  "window_share": len(acct_windows[a]) / nwin}
                 for a in sorted(d_tot, key=d_tot.get, reverse=True)[:8]]
    ref_tot = {a: sum(v.values()) for a, v in w_ref.items()}
    ref_all = Z()
    for v in w_ref.values():
        for k, x in v.items():
            ref_all[k] += x
    ref_rows = [{"tag": a, "events": referral[a], "share": ratio_ci(w_ref[a], ref_all, rng, ks)}
                for a in sorted(ref_tot, key=ref_tot.get, reverse=True)[:8]]

    def chain_table(by, den):
        tot = {c: sum(v.values()) for c, v in by.items()}
        rows = [{"chain": c, "usd_sample": tot[c], "share": ratio_ci(by[c], den, rng, ks)}
                for c in sorted(tot, key=tot.get, reverse=True)[:12]]
        return rows, hhi(tot)

    dep_rows, dep_hhi = chain_table(w_dep_chain, w_dep)
    wd_rows, wd_hhi = chain_table(w_wd_chain, w_wd)
    asset_tot = {s: sum(v.values()) for s, v in w_asset.items()}
    asset_rows = [{"symbol": s, "share": ratio_ci(w_asset[s], w_transfer_usd, rng, ks)}
                  for s in sorted(asset_tot, key=asset_tot.get, reverse=True)[:10]]
    sig_tot = {s: sum(v.values()) for s, v in w_signer.items()}
    sig_rows = [{"signer": s, "type": acct_type(s), "share": ratio_ci(w_signer[s], w_tx, rng, ks)}
                for s in sorted(sig_tot, key=sig_tot.get, reverse=True)[:8]]
    top5_sig = Z()
    for s in sorted(sig_tot, key=sig_tot.get, reverse=True)[:5]:
        for k, v in w_signer[s].items():
            top5_sig[k] += v
    src_rows = [{"type": s, "share": ratio_ci(v, w_transfer_usd, rng, ks)} for s, v in
                sorted(w_srctype.items(), key=lambda kv: -sum(kv[1].values()))]

    sizes.sort()
    q = lambda p: sizes[min(len(sizes) - 1, int(p * len(sizes)))] if sizes else None

    # daily estimates from the sample (windows of that UTC day only)
    by_day = collections.defaultdict(list)
    for k in ks:
        if k in win_day:
            by_day[win_day[k]].append(k)
    blocks_per_day = 86400 / 0.6
    daily = []
    for d in days:
        kk = by_day[d]
        if len(kk) < 0.8 * blocks_per_day / S:      # partial days at the edges are dropped
            continue
        f = blocks_per_day / (len(kk) * W)
        daily.append({"date": d, "windows": len(kk),
                      "tx": sum(w_tx[k] for k in kk) * f,
                      "transfer_usd": sum(w_transfer_usd[k] for k in kk) * f,
                      "shield_usd": sum(w_shield[k] for k in kk) * f,
                      "public_swap_usd": sum(w_diff[k] for k in kk) * f / 2,
                      "deposit_usd": sum(w_dep[k] for k in kk) * f,
                      "withdraw_usd": sum(w_wd[k] for k in kk) * f})

    # public series
    L = json.load(open(os.path.join(PUB, "defillama.json")))
    vol = {day(t): v for t, v in L["volume"]}
    fees = {day(t): v for t, v in L["fees"]}
    rev = {day(t): v for t, v in L["revenue"]}
    price = {day(t): v for t, v in L["near_price"]}
    chain_fees = {day(t): v for t, v in L["near_chain_fees"]}
    cnt_p = os.path.join(PUB, "intents_tx_counts.json")
    counts = {}
    if os.path.exists(cnt_p):
        counts = {day(r[0]): r[1] for r in json.load(open(cnt_p))["rows"]}

    for r in daily:
        r["llama_volume"] = vol.get(r["date"]) or None   # 0 means "not published yet"
        r["exact_tx"] = counts.get(r["date"])
    both = [r for r in daily if r["llama_volume"]]
    recon = {}
    if both:
        lv = sum(r["llama_volume"] for r in both)
        for key in ("transfer_usd", "deposit_usd", "withdraw_usd"):
            recon[key + "_over_published_volume"] = sum(r[key] for r in both) / lv
        recon["days_compared"] = len(both)
        recon["published_volume_per_day"] = lv / len(both)
        recon["corr_deposit_vs_published"] = corr([r["deposit_usd"] for r in both],
                                                  [r["llama_volume"] for r in both])
        recon["corr_transfer_vs_published"] = corr([r["transfer_usd"] for r in both],
                                                   [r["llama_volume"] for r in both])
    if both:
        cmp_days = {r["date"] for r in both}
        ks_cmp = [k for k in ks if win_day.get(k) in cmp_days]
        lv = sum(r["llama_volume"] for r in both)
        p_, lo_, hi_ = total_ci(w_dep, rng, ks_cmp, scale)
        recon["deposit_over_published"] = [p_ / lv, lo_ / lv, hi_ / lv]
        p_, lo_, hi_ = total_ci(w_wd, rng, ks_cmp, scale)
        recon["withdraw_over_published"] = [p_ / lv, lo_ / lv, hi_ / lv]
        p_, lo_, hi_ = total_ci(w_shield, rng, ks_cmp, scale)
        recon["shield_over_published"] = [p_ / lv, lo_ / lv, hi_ / lv]
    txcheck = [r for r in daily if r.get("exact_tx")]
    if txcheck:
        recon["sample_tx_over_exact_tx"] = sum(r["tx"] for r in txcheck) / sum(r["exact_tx"] for r in txcheck)
        recon["tx_days_compared"] = len(txcheck)

    # public long-run series (monthly) for value capture context
    months = collections.OrderedDict()
    for d in sorted(vol):
        m = months.setdefault(d[:7], {"month": d[:7], "volume": 0.0, "fees": 0.0, "revenue": 0.0,
                                      "chain_fees": 0.0, "days": 0, "price_sum": 0.0, "price_n": 0})
        m["volume"] += vol[d] or 0
        m["fees"] += fees.get(d, 0) or 0
        m["revenue"] += rev.get(d, 0) or 0
        m["chain_fees"] += chain_fees.get(d, 0) or 0
        m["days"] += 1
        if d in price:
            m["price_sum"] += price[d]
            m["price_n"] += 1
    monthly = []
    for m in months.values():
        m["price"] = m["price_sum"] / m["price_n"] if m["price_n"] else None
        m["fee_bps"] = m["fees"] / m["volume"] * 1e4 if m["volume"] else None
        m["rev_bps"] = m["revenue"] / m["volume"] * 1e4 if m["volume"] else None
        del m["price_sum"], m["price_n"]
        monthly.append(m)
    last30 = sorted(vol)[-31:-1]
    v30 = sum(vol[d] or 0 for d in last30)
    f30 = sum(fees.get(d, 0) or 0 for d in last30)
    r30 = sum(rev.get(d, 0) or 0 for d in last30)
    public = {"window": [last30[0], last30[-1]], "volume_30d": v30, "fees_30d": f30,
              "revenue_30d": r30, "fee_bps_30d": f30 / v30 * 1e4, "rev_bps_30d": r30 / v30 * 1e4,
              "revenue_share_of_fees_30d": r30 / f30 if f30 else None,
              "chain_fees_30d": sum(chain_fees.get(d, 0) or 0 for d in last30),
              "annualised_revenue": r30 * 365 / 30, "near_price_last": price[sorted(price)[-1]],
              "fetched_at": L["fetched_at"]}
    # the official track hypothesis: does volume lead usage (tx count) better than price does?
    lead = {}
    if counts:
        ds = [d for d in sorted(counts) if d in vol and d in price][:-1]
        if len(ds) > 12:
            dlog = lambda xs: [math.log(b / a) for a, b in zip(xs, xs[1:]) if a > 0 and b > 0]
            tx_c = dlog([counts[d] for d in ds])
            vo_c = dlog([vol[d] for d in ds])
            px_c = dlog([price[d] for d in ds])
            n = min(len(tx_c), len(vo_c), len(px_c))
            tx_c, vo_c, px_c = tx_c[:n], vo_c[:n], px_c[:n]
            lead = {"days": len(ds), "from": ds[0], "to": ds[-1],
                    "corr_tx_vs_volume_same_day": corr(tx_c, vo_c),
                    "corr_tx_vs_price_same_day": corr(tx_c, px_c),
                    "corr_tx_vs_volume_prev_day": corr(tx_c[1:], vo_c[:-1]),
                    "corr_tx_vs_price_prev_day": corr(tx_c[1:], px_c[:-1]),
                    "corr_levels_tx_volume": corr([counts[d] for d in ds], [vol[d] for d in ds]),
                    "corr_levels_tx_price": corr([counts[d] for d in ds], [price[d] for d in ds])}

    out = {
        "generated_from": {"sample_config": cfg, "windows_used": nwin,
                           "windows_drawn": cfg["n_strata"] if cfg else nwin,
                           "transactions": len(txs), "first_day": day(min(p[1] for p in pts)),
                           "last_day": day(max(p[1] for p in pts)), "span_days": span_days,
                           "expansion_factor": scale, "bootstrap_draws": BOOT,
                           "sample_dir": raw, "price_mode": price_mode, "cap": cap, "half": half,
                           "legs_priced_at_day_price": pr.at_day / max(1, pr.hit),
                           "priced_token_legs": pr.hit, "unpriced_token_legs": pr.miss,
                           "price_coverage": pr.hit / max(1, pr.hit + pr.miss),
                           "unpriced_top": pr.missing.most_common(8)},
        "events": dict(ev_count.most_common()),
        "totals_per_day": {"transactions": per_day(w_tx), "transfer_usd": per_day(w_transfer_usd),
                           "deposit_usd": per_day(w_dep), "withdraw_usd": per_day(w_wd),
                           "token_diff_usd": per_day(w_diff)},
        "reconciliation": recon,
        "ledger": {"receivers": r_rows, "senders": s_rows,
                   "top1_receiver_share": r_rows[0]["share"],
                   "top3_receiver_share": cum_share(r_order, w_recv, 3),
                   "top1_sender_share": s_rows[0]["share"],
                   "top3_sender_share": cum_share(s_order, w_sent, 3),
                   "top5_sender_share": cum_share(s_order, w_sent, 5),
                   "receiver_hhi": hhi(r_tot), "sender_hhi": hhi(s_tot),
                   "distinct_senders": len(s_tot), "distinct_receivers": len(r_tot),
                   "top1_either_side": either, "token_diff_accounts": diff_rows,
                   "distinct_token_diff_accounts": len(d_tot),
                   "transfers": n_transfers, "transfers_with_opaque_memo": n_memo,
                   "token_diff_share_of_events": ev_count.get("dip4:token_diff", 0) /
                   max(1, ev_count.get("dip4:token_diff", 0) + ev_count.get("dip4:transfer", 0))},
        "confidential": {
            "treasury": TREASURY, "label": KNOWN[TREASURY]["label"], "source": KNOWN[TREASURY]["source"],
            "shield_usd_per_day": per_day(w_shield), "unshield_usd_per_day": per_day(w_unshield),
            "shield_share_of_transfers": ratio_ci(w_shield, w_transfer_usd, rng, ks),
            "unshield_share_of_transfers": ratio_ci(w_unshield, w_transfer_usd, rng, ks),
            "shield_transfers_per_day": per_day(w_shield_n),
            "shield_with_encrypted_memo": ratio_ci(w_shield_memo, w_shield_n, rng, ks),
            "shield_sources": [{"type": t_, "share": ratio_ci(v_, w_shield, rng, ks)}
                               for t_, v_ in sorted(w_shield_src.items(), key=lambda kv: -sum(kv[1].values()))],
            # value settled by swaps that are visible on the public contract (each swap counted once)
            "public_swap_usd_per_day": [x / 2 for x in per_day(w_diff)],
            "shield_vs_public_swaps": ratio_ci(w_shield, {k: w_shield.get(k, 0) + w_diff.get(k, 0) / 2
                                                          for k in set(w_shield) | set(w_diff)}, rng, ks)},
        "known_accounts": KNOWN,
        "standing": {"threshold_windows": thresh, "count": len(standing), "accounts": stand_rows,
                     "share_touching_standing": ratio_ci(num_touch, w_transfer_usd, rng, ks),
                     "share_between_standing": ratio_ci(num_both, w_transfer_usd, rng, ks),
                     "accounts_seen": len(acct_windows),
                     "accounts_seen_once": sum(1 for w in acct_windows.values() if len(w) == 1)},
        "chains": {"deposits": dep_rows, "withdrawals": wd_rows, "deposit_hhi": dep_hhi,
                   "withdrawal_hhi": wd_hhi},
        "assets": {"top": asset_rows, "stable_share": ratio_ci(w_stable, w_transfer_usd, rng, ks)},
        "access": {"signers": sig_rows, "top5_signer_share": ratio_ci(top5_sig, w_tx, rng, ks),
                   "self_signed_share": ratio_ci(w_self, w_tx, rng, ks),
                   "distinct_signers": len(sig_tot), "source_account_types": src_rows},
        "sizes": {"n": len(sizes), "median": q(0.5), "p90": q(0.9), "p99": q(0.99),
                  "max": sizes[-1] if sizes else None,
                  "share_from_100k_plus": ratio_ci(w_big, w_transfer_usd, rng, ks)},
        "referrals": ref_rows, "referral_events": sum(referral.values()),
        "token_diff_events": ev_count.get("dip4:token_diff", 0),
        "daily": daily, "monthly": monthly, "public": public, "lead": lead,
        "exact_tx_counts": [[d, counts[d]] for d in sorted(counts)],
        "daily_public": [[d, vol[d], price.get(d)] for d in sorted(vol)[-180:]],
    }
    # ---- when did swaps leave the public contract? (computed last so earlier bootstrap draws are unchanged)
    w_swap_tx = collections.Counter()
    for t in txs:
        if any(ev[0] == "dip4" and ev[1] == "token_diff" for ev in t["ev"]):
            w_swap_tx[t["k"]] += 1
    for r in daily:
        kk = by_day[r["date"]]
        r["swap_tx_share"] = sum(w_swap_tx[k] for k in kk) / max(1, sum(w_tx[k] for k in kk))
    sw = None
    if len(daily) >= 12:
        xs = [r["swap_tx_share"] for r in daily]
        best = None
        for i in range(5, len(xs) - 4):          # at least 5 days on each side
            a_, b_ = xs[:i], xs[i:]
            ma, mb = sum(a_) / len(a_), sum(b_) / len(b_)
            sse = sum((x - ma) ** 2 for x in a_) + sum((x - mb) ** 2 for x in b_)
            if best is None or sse < best[0]:
                best = (sse, i)
        i = best[1]
        d0 = daily[i]["date"]

        def period(rows):
            ds = {r["date"] for r in rows}
            kp = [k for k in ks if win_day.get(k) in ds]
            both_w = {k: w_shield.get(k, 0) + w_diff.get(k, 0) / 2 for k in kp}
            nd = len(kp) * S / blocks_per_day
            sh, pb = total_ci(w_shield, rng, kp, scale), total_ci(w_diff, rng, kp, scale)
            lv = sum(r["llama_volume"] or 0 for r in rows)
            n_l = sum(1 for r in rows if r["llama_volume"])
            o_ = {"from": rows[0]["date"], "to": rows[-1]["date"], "days": len(rows), "windows": len(kp),
                  "swap_tx_share": ratio_ci(w_swap_tx, w_tx, rng, kp),
                  "public_swap_usd_per_day": [x / 2 / nd for x in pb],
                  "shield_usd_per_day": [x / nd for x in sh],
                  "shield_vs_public": ratio_ci(w_shield, both_w, rng, kp),
                  "published_volume_per_day": lv / n_l if n_l else None}
            if n_l:
                pubs = sum(r["public_swap_usd"] for r in rows if r["llama_volume"])
                o_["public_swap_over_published"] = pubs / lv
            return o_
        sw = {"first_day_after": d0, "method": "the split of the daily series that minimises within-period variance of the "
              "share of transactions carrying a dip4:token_diff event, with at least 5 days on each side",
              "before": period(daily[:i]), "after": period(daily[i:])}
    if sw:
        # how sure is the break date? resample windows within each day, redo the split each time
        cnt = collections.Counter()
        dd = [r["date"] for r in daily]
        for _ in range(1000):
            xs = []
            for d in dd:
                kk = by_day[d]
                pick = [kk[rng.randrange(len(kk))] for _ in kk]
                xs.append(sum(w_swap_tx[k] for k in pick) / max(1, sum(w_tx[k] for k in pick)))
            bb = None
            for j in range(5, len(xs) - 4):
                a_, b_ = xs[:j], xs[j:]
                ma, mb = sum(a_) / len(a_), sum(b_) / len(b_)
                sse = sum((x - ma) ** 2 for x in a_) + sum((x - mb) ** 2 for x in b_)
                if bb is None or sse < bb[0]:
                    bb = (sse, j)
            cnt[dd[bb[1]]] += 1
        order = sorted(cnt)
        acc, lo, hi = 0, None, None
        for d in order:
            acc += cnt[d]
            if lo is None and acc >= 25:
                lo = d
            if hi is None and acc >= 975:
                hi = d
        sw["break_date_bootstrap"] = {"draws": 1000, "range_95": [lo, hi], "share_on_point_estimate": cnt[sw["first_day_after"]] / 1000,
                                      "distribution": [[d, cnt[d] / 1000] for d in order]}
    if sw:
        for part in ("before", "after"):
            ds = [r["date"] for r in daily if sw[part]["from"] <= r["date"] <= sw[part]["to"] and vol.get(r["date"])]
            v_, r_, f_ = (sum(x.get(d, 0) or 0 for d in ds) for x in (vol, rev, fees))
            sw[part]["rev_bps"] = r_ / v_ * 1e4 if v_ else None
            sw[part]["fee_bps"] = f_ / v_ * 1e4 if v_ else None
    out["switch"] = sw
    # when is it used? share of sampled transactions by UTC hour and weekday (every window has equal weight)
    hrs, wds = collections.Counter(), collections.Counter()
    for t in txs:
        tm = time.gmtime(t["t"])
        hrs[tm.tm_hour] += 1
        wds[tm.tm_wday] += 1
    out["timing"] = {"by_utc_hour": [hrs[h] / max(1, len(txs)) for h in range(24)],
                     "by_weekday_mon0": [wds[d] / max(1, len(txs)) for d in range(7)]}
    # memo check: the sampler keeps only the LENGTH of memos longer than 40 characters ("<184 chars>")
    mc = collections.Counter()
    for t in txs:
        for ev in t["ev"]:
            if ev[0] == "dip4" and ev[1] == "transfer":
                for it in items(ev[2]):
                    long_ = str(it.get("memo", "")).startswith("<")
                    mc[("shield" if it.get("receiver_id") == TREASURY else "other", long_)] += 1
    out["confidential"]["memo_check"] = {"shield_transfers": mc[("shield", True)] + mc[("shield", False)], "shield_with_long_memo": mc[("shield", True)],
                                         "other_transfers": mc[("other", True)] + mc[("other", False)], "other_with_long_memo": mc[("other", True)],
                                         "note": "long = over 40 characters; only the length is stored. One memo re-fetched in full (tx HRAiDXqSVGeUDUFsQcyACdUN2F2aXHbBnBhD6ZFB5gV4) is 184 characters of base64 data."}
    # who shields? broad use or a few accounts (computed last: earlier draws unchanged)
    tot_sh = {a: sum(v.values()) for a, v in w_shield_acct.items()}
    top_sh = sorted(tot_sh, key=tot_sh.get, reverse=True)
    n10 = collections.Counter()
    for a in top_sh[:10]:
        n10.update(w_shield_acct[a])
    out["confidential"]["shielders"] = {
        "distinct_in_sample": len(tot_sh),
        "top10_share": ratio_ci(n10, w_shield, rng, ks),
        "top": [{"account": a, "type": acct_type(a), "share": ratio_ci(w_shield_acct[a], w_shield, rng, ks),
                 "windows": len(w_shield_acct[a])} for a in top_sh[:8]],
        "accounts_under_1pct_share": 1 - sum(tot_sh[a] for a in top_sh if tot_sh[a] >= 0.01 * sum(tot_sh.values())) / max(1e-9, sum(tot_sh.values()))}
    if write:
        json.dump(out, open(os.path.join(DER, "numbers.json"), "w"), indent=1)
        print("wrote data/derived/numbers.json:", len(txs), "txs,", nwin, "windows")
    return out


def key_metrics(o):
    """The figures behind tests T1-T5 plus the router share, for the robustness table."""
    return {"windows": o["generated_from"]["windows_used"], "transactions": o["generated_from"]["transactions"],
            "T1": o["reconciliation"].get("deposit_over_published"),
            "T2": o["chains"]["deposits"][0]["share"], "T2_chain": o["chains"]["deposits"][0]["chain"],
            "T2_chains": {r["chain"]: r["share"] for r in o["chains"]["deposits"][:6]},
            "T3": o["assets"]["stable_share"], "T4": o["ledger"]["top1_sender_share"],
            "T4_account": o["ledger"]["senders"][0]["account"],
            "T5": o["access"]["top5_signer_share"], "router": o["ledger"]["top1_either_side"]["share"],
            "shield_vs_public": o["confidential"]["shield_vs_public_swaps"],
            "shield_over_published": o["reconciliation"].get("shield_over_published"),
            "router_account": o["ledger"]["top1_either_side"]["account"],
            "tx_check": o["reconciliation"].get("sample_tx_over_exact_tx")}


def main():
    out = run(write=False)
    rob = [{"name": "Main sample", "what": "720 windows, seed 20261114, valued at each day's price",
            **key_metrics(out)}]
    variants = [("Replication sample", "an independent second sample of the same 30 days: different seed, 360 windows",
                 dict(raw="raw_b")),
                ("Third sample", "a third independent sample of the same 30 days, drawn AFTER the verdict rule was fixed: seed 31337, 360 windows",
                 dict(raw="raw_c")),
                ("Older half only", "main sample, the earlier 15 days", dict(half="older")),
                ("Recent half only", "main sample, the later 15 days", dict(half="recent")),
                ("Whales removed", "main sample without any single item worth $100K or more", dict(cap=100_000)),
                ("Prices at fetch time", "main sample valued at one price list instead of daily prices",
                 dict(price_mode="spot"))]
    for name, what, kw in variants:
        d = os.path.join(ROOT, "data", kw.get("raw", "raw"))
        if not os.path.exists(os.path.join(d, "sample_txs.jsonl")):
            continue
        try:
            o = run(write=False, boot=500, **kw)
        except SystemExit:
            continue
        if kw.get("raw") and o["generated_from"]["windows_used"] < 0.9 * o["generated_from"]["windows_drawn"]:
            continue    # replication not finished downloading
        rob.append({"name": name, "what": what, **key_metrics(o)})
        print("variant done:", name, flush=True)
    # fixed-effect (inverse-variance) pooling of the two independent samples
    repl = next((r for r in rob if r["name"] == "Replication sample"), None)
    if repl:
        def pool(a, b):
            if not a or not b or None in a or None in b:
                return None
            sa, sb = max((a[2] - a[1]) / 3.92, 1e-9), max((b[2] - b[1]) / 3.92, 1e-9)
            wa, wb = 1 / sa ** 2, 1 / sb ** 2
            m, se = (a[0] * wa + b[0] * wb) / (wa + wb), (1 / (wa + wb)) ** 0.5
            return [m, m - 1.96 * se, m + 1.96 * se]
        pooled = {"name": "Pooled (main + replication)",
                  "what": "inverse-variance average of the two independent samples, 1,080 windows",
                  "windows": rob[0]["windows"] + repl["windows"],
                  "transactions": rob[0]["transactions"] + repl["transactions"]}
        for t in ("T1", "T3", "T4", "T5", "router", "shield_vs_public", "shield_over_published"):
            pooled[t] = pool(rob[0][t], repl[t]) if rob[0]["T4_account"] == repl["T4_account"] or t != "T4" else None
        chains = {c: pool(rob[0]["T2_chains"].get(c), repl["T2_chains"].get(c))
                  for c in rob[0]["T2_chains"] if c in repl["T2_chains"]}
        chains = {c: v for c, v in chains.items() if v}
        top = max(chains, key=lambda c: chains[c][0])
        pooled.update({"T2": chains[top], "T2_chain": top, "T2_chains": chains, "tx_check": None,
                       "T4_account": rob[0]["T4_account"], "router_account": rob[0]["router_account"]})
        rob.insert(2, pooled)
        third = next((r for r in rob if r["name"] == "Third sample"), None)
        if third:
            def pool3(k):
                xs = [r_[k] for r_ in (rob[0], repl, third)]
                if any((not x) or None in x for x in xs):
                    return None
                ws = [1 / max((x[2] - x[1]) / 3.92, 1e-9) ** 2 for x in xs]
                m = sum(x[0] * w for x, w in zip(xs, ws)) / sum(ws)
                se = (1 / sum(ws)) ** 0.5
                return [m, m - 1.96 * se, m + 1.96 * se]
            p3 = {"name": "Pooled (all three samples)", "what": "inverse-variance average of the three independent samples, 1,440 windows",
                  "windows": rob[0]["windows"] + repl["windows"] + third["windows"],
                  "transactions": rob[0]["transactions"] + repl["transactions"] + third["transactions"]}
            for t in ("T1", "T3", "T5", "router", "shield_vs_public", "shield_over_published"):
                p3[t] = pool3(t)
            p3["T4"] = pool3("T4") if rob[0]["T4_account"] == repl["T4_account"] == third["T4_account"] else None
            ch3 = {}
            for c in rob[0]["T2_chains"]:
                if c in repl["T2_chains"] and c in third["T2_chains"]:
                    xs = [r_["T2_chains"][c] for r_ in (rob[0], repl, third)]
                    ws = [1 / max((x[2] - x[1]) / 3.92, 1e-9) ** 2 for x in xs]
                    m = sum(x[0] * w for x, w in zip(xs, ws)) / sum(ws)
                    se = (1 / sum(ws)) ** 0.5
                    ch3[c] = [m, m - 1.96 * se, m + 1.96 * se]
            top3 = max(ch3, key=lambda c: ch3[c][0])
            p3.update({"T2": ch3[top3], "T2_chain": top3, "T2_chains": ch3, "tx_check": None,
                       "T4_account": rob[0]["T4_account"], "router_account": rob[0]["router_account"]})
            rob.insert(rob.index(third) + 1, p3)
    out["robustness"] = rob
    json.dump(out, open(os.path.join(DER, "numbers.json"), "w"), indent=1)
    print("wrote data/derived/numbers.json:", out["generated_from"]["transactions"], "txs,",
          out["generated_from"]["windows_used"], "windows")


def corr(x, y):
    n = min(len(x), len(y))
    if n < 3:
        return None
    x, y = x[:n], y[:n]
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if not sx or not sy:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


if __name__ == "__main__":
    main()
