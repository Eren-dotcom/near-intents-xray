#!/usr/bin/env python3
"""Render data/derived/numbers.json into docs/index.html (one self-contained file, inline SVG, no
network requests) and THESIS.md. No number is typed by hand: prose is a template filled from
numbers.json, and verdicts come from thesis_tests.json."""
import datetime as dt, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charts import *  # noqa: F401,F403
from charts import N, ROOT, C1, C2, C3, GOOD, BAD, WARN, INK, MUTE, LINE, BG, e

G, LED, ST, CH, AS, AC, SZ, PUB, RC, TPD = (N["generated_from"], N["ledger"], N["standing"], N["chains"],
                                            N["assets"], N["access"], N["sizes"], N["public"],
                                            N["reconciliation"], N["totals_per_day"])
V = {v["id"]: v for v in verdicts()}
# Headline rule for the sample-based tests (T1-T5), using both independent samples:
#   1. judge the POOLED interval (main + replication) against the threshold;
#   2. downgrade to "inconclusive" if either sample's own point estimate is on the other side.
TBY = {t["id"]: t for t in TESTS}
ROB = N.get("robustness", [])
REPL = next((r for r in ROB if r["name"] == "Replication sample"), None)
POOL = next((r for r in ROB if r["name"].startswith("Pooled")), None)


def side(t, p):
    """Which side of the rule a bare point estimate falls on."""
    return judge(t, [p, p, p])[0]


for _t, _v in V.items():
    _v["main"], _v["repl"], _v["pooled"] = _v["verdict"], None, None
    _v["main_val"] = [_v["value"], _v["lo"], _v["hi"]]
    if REPL and POOL and REPL.get(_t) and POOL.get(_t):
        _v["repl"] = judge(TBY[_t], REPL[_t])[0]
        verdict, p, lo, hi = judge(TBY[_t], POOL[_t])
        _v["pooled"] = verdict
        if side(TBY[_t], _v["value"]) != side(TBY[_t], REPL[_t][0]):
            verdict = "inconclusive"
        _v.update({"verdict": verdict, "value": p, "lo": lo, "hi": hi})
hub_s, hub_r = LED["senders"][0], LED["receivers"][0]
same_hub = hub_s["account"] == hub_r["account"]
dep0, wd0 = CH["deposits"][0], CH["withdrawals"][0]
CHAIN_NAMES = {"eth": "Ethereum", "sol": "Solana", "btc": "Bitcoin", "bsc": "BNB Chain", "arb": "Arbitrum",
               "near": "NEAR", "tron": "Tron", "zec": "Zcash", "base": "Base", "pol": "Polygon",
               "ton": "TON", "op": "Optimism", "avax": "Avalanche", "ltc": "Litecoin", "doge": "Dogecoin",
               "xrp": "XRP Ledger", "sui": "Sui", "cardano": "Cardano", "bch": "Bitcoin Cash",
               "gnosis": "Gnosis", "bera": "Berachain", "aptos": "Aptos", "stellar": "Stellar",
               "hypercore": "Hyperliquid", "monad": "Monad", "plasma": "Plasma", "starknet": "Starknet"}
cn = lambda c: CHAIN_NAMES.get(c, c)
ratio = lambda x: "n/a" if x is None else f"{x:.2f}×"
r2 = lambda x: "n/a" if x is None else f"{x:+.2f}"
bps = lambda x, d=1: "n/a" if x is None else f"{x:.{d}f} bps"

TOP3 = ", ".join(f"{cn(r['chain'])} {pct(r['share'][0], 0)}" for r in CH["deposits"][:3])
EI = LED["top1_either_side"]
CF = N["confidential"]
KNOWN = N.get("known_accounts", {})
IS_TREASURY = EI["account"] == CF["treasury"]
PSV = POOL["shield_vs_public"] if POOL and POOL.get("shield_vs_public") else CF["shield_vs_public_swaps"]
PSP = POOL["shield_over_published"] if POOL and POOL.get("shield_over_published") else RC.get("shield_over_published")
OLD = next((r for r in ROB if r["name"] == "Older half only"), None)
NEW = next((r for r in ROB if r["name"] == "Recent half only"), None)
TREND = (f" In the main sample the share was {pct(OLD['shield_vs_public'][0], 0)} in the earlier 15 days and {pct(NEW['shield_vs_public'][0], 0)} in the later 15."
         if OLD and NEW and OLD.get("shield_vs_public") and NEW.get("shield_vs_public") else "")
_mc = CF.get("memo_check")
MEMO_TXT = (f"Every one of the {num(_mc['shield_with_long_memo'])} sampled transfers into it carries a long opaque memo (120 to 184 characters), and "
            f"{'none' if _mc['other_with_long_memo'] == 0 else num(_mc['other_with_long_memo'])} of the {num(_mc['other_transfers'])} other transfers does. "
            "That matches the documentation, which says the shield memo carries the encrypted recipient. We stored only the memo's length; the one we re-fetched in full is base64 data."
            if _mc and _mc["shield_with_long_memo"] == _mc["shield_transfers"] else
            "Transfers into it carry a long opaque memo, as the documentation describes for the encrypted recipient.")
if EI["share"][0] > 0.5 and IS_TREASURY:
    ROUTER = (f"But read it with this: that account is on one side or the other of {ci(EI['share'])} of the value, and it is not an anonymous whale. "
              f"NEAR's own documentation names it as the Confidential Intents Treasury: a transfer into it is the \"shield\" step that moves funds onto "
              f"the confidential ledger, and a transfer out of it is the unshield. {MEMO_TXT}")
elif EI["share"][0] > 0.5:
    ROUTER = (f"But read it with this: the same account, {short(EI['account'])}, is on one side or the other of {ci(EI['share'])} of the value. "
              "It behaves like a single router in front of the solvers.")
else:
    ROUTER = f"The account most often on either side of a transfer, {short(EI['account'])}, is a party to {ci(EI['share'])} of the value."
CONF_TXT = (f"About {usd(CF['shield_usd_per_day'][0], 0)} a day is shielded into Confidential Intents ({usd(CF['shield_usd_per_day'][1], 0)} to {usd(CF['shield_usd_per_day'][2], 0)}), "
            f"in roughly {num(CF['shield_transfers_per_day'][0])} transfers a day. Swaps that settle in the open on the public contract come to about "
            f"{usd(CF['public_swap_usd_per_day'][0], 0)} a day. So of the value we can see being settled either way, {ci(PSV)} goes to the confidential side "
            f"(two samples pooled).{TREND}")
# ---------- sentences that depend on a verdict ----------
def vtext(tid, sup, con, inc):
    v = V[tid]
    txt = {"supported": sup, "contradicted": con, "inconclusive": inc, "no data": "No data."}[v["main"]]
    if v["repl"]:
        f = ratio if tid == "T1" else pct
        r, q = REPL[tid], POOL[tid]
        extra = f", led by {cn(REPL['T2_chain'])}" if tid == "T2" else ""
        txt += (f" The independent replication sample measures {f(r[0])} (95% CI {f(r[1])} to {f(r[2])}){extra}; "
                f"pooling both samples gives {f(q[0])} ({f(q[1])} to {f(q[2])}).")
        if v["verdict"] != v["pooled"]:
            txt += (" The two samples' point estimates fall on opposite sides of the threshold, so the claim is marked "
                    "inconclusive even though the pooled interval passes.")
        elif v["verdict"] == v["main"]:
            txt += " The verdict holds."
    return txt


T_TXT = {
 "T1": vtext("T1",
   f"Value entering the contract in our sample is {ci(RC['deposit_over_published'], ratio)} of the volume NEAR publishes for the same {RC['days_compared']} days. The headline number is not an artefact of a dashboard: money of that order shows up on-chain. A second check agrees: the sample's transaction count is {ratio(RC.get('sample_tx_over_exact_tx'))} the exact count.",
   f"Value entering the contract in our sample is {ci(RC['deposit_over_published'], ratio)} of the published volume for the same days, outside the 0.5×–2× band. Either the published figure counts something the contract does not see, or our deposit definition misses a path.",
   f"Value entering the contract in our sample is {ci(RC['deposit_over_published'], ratio)} of the published volume. The point estimate is inside the 0.5×–2× band but the interval is not, so the sample cannot confirm it."),
 "T2": vtext("T2",
   f"The largest source chain, {cn(dep0['chain'])}, supplies {ci(dep0['share'])} of deposits. The top three ({TOP3}) are close enough that the leader changes between robustness runs; none comes near half. Demand does not hang on one chain.",
   f"{cn(dep0['chain'])} alone supplies {ci(dep0['share'])} of deposits. The 'any chain' story is, in dollars, mostly a one-chain story.",
   f"{cn(dep0['chain'])} supplies {ci(dep0['share'])} of deposits. The interval straddles one half, so the sample cannot say whether one chain dominates."),
 "T3": vtext("T3",
   f"Stablecoins are {ci(AS['stable_share'])} of the value moved inside the ledger. This is a dollar-transfer product more than a trading venue.",
   f"Stablecoins are only {ci(AS['stable_share'])} of the value moved. The flow is driven by volatile assets.",
   f"Stablecoins are {ci(AS['stable_share'])} of the value moved; the interval straddles one half."),
 "T4": vtext("T4",
   f"The largest sender moves {ci(LED['top1_sender_share'])} of the value, so the test as written passes: no single account sends half. " + ROUTER,
   f"One account, {short(hub_s['account'])}, sends {ci(LED['top1_sender_share'])} of all value moved inside the ledger. " + ROUTER,
   f"The largest sender, {short(hub_s['account'])}, moves {ci(LED['top1_sender_share'])} of the value; the interval straddles one half. " + ROUTER),
 "T5": vtext("T5",
   f"The five busiest signers submit {ci(AC['top5_signer_share'])} of transactions; access is spread out.",
   f"Five accounts submit {ci(AC['top5_signer_share'])} of every transaction that touches the contract. End users almost never sign a NEAR transaction themselves ({pct(AC['self_signed_share'][0])} of transactions are signed by an unnamed user account).",
   f"The five busiest signers submit {ci(AC['top5_signer_share'])} of transactions; the interval straddles 90%."),
 "T6": vtext("T6",
   f"NEAR's captured revenue is {bps(PUB['rev_bps_30d'])} of volume over the last 30 days.",
   f"NEAR's captured revenue is {bps(PUB['rev_bps_30d'])} of volume over the last 30 days: {usd(PUB['revenue_30d'])} on {usd(PUB['volume_30d'])}. Users pay {bps(PUB['fee_bps_30d'])}; NEAR keeps {pct(PUB['revenue_share_of_fees_30d'])} of that.",
   "Inconclusive."),
}
demand_ok = [t for t in ("T1", "T2", "T3") if V[t]["verdict"] == "supported"]
struct_bad = [t for t in ("T4", "T5", "T6") if V[t]["verdict"] == "contradicted"]
RISK = {"T4": "one account settles most of the value",
        "T5": f"five relayer accounts submit {pct(AC['top5_signer_share'][0], 0)} of all transactions",
        "T6": f"NEAR keeps only {bps(PUB['rev_bps_30d'])} of the volume"}
WATCH = {"T4": "spreads settlement across more accounts", "T5": "opens up who can submit transactions",
         "T6": "raises its take"}
DEMAND = {"T1": "it reconciles with the published volume", "T2": "it comes from many chains",
          "T3": "most of it is stablecoins, so it behaves like a cross-chain dollar rail"}


def join(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


RSH = POOL["router"] if POOL and POOL.get("router") else EI["share"]
unsettled = [t for t in ("T1", "T2", "T3") if V[t]["verdict"] == "inconclusive"]
UNS = {"T1": "whether it reconciles with the published volume", "T2": "whether any one chain supplies half of it",
       "T3": "whether stablecoins are most of it"}
if len(demand_ok) >= 2 and struct_bad:
    VIEW = (f"The demand is real; the weak points are structural. On-chain flow passes {len(demand_ok)} of 3 demand "
            f"tests: {join(DEMAND[t] for t in demand_ok)}" + (f" ({join(UNS[t] for t in unsettled)} is not settled by two samples)" if unsettled else "") + ". That is the bull case, and it is checkable. The structure fails "
            f"{len(struct_bad)} of 3 tests: {join(RISK[t] for t in struct_bad)}. So the long-term case for the NEAR token is not "
            f"\"Intents volume goes up\". It is \"NEAR {join(WATCH[t] for t in struct_bad)} without losing the volume\". "
            "This repository measures each of those, and can be re-run to see whether they move."
            + (f" And one finding cuts both ways: {pct(PSV[0], 0)} of the value we can see being settled now moves through Confidential Intents, a ledger outsiders cannot audit. That is real demand for privacy, and it also means the public evidence this thesis rests on is shrinking." if IS_TREASURY and PSV[0] > 0.5 else ""))
elif len(demand_ok) >= 2:
    VIEW = (f"The demand is real ({join(DEMAND[t] for t in demand_ok)}), and none of the three structural tests came out against. "
            "On this evidence the bull case is the simple one: verifiable cross-chain flow on a market that is not controlled "
            "by a handful of accounts.")
else:
    VIEW = ("The sample does not support the demand story strongly enough to build a long-term case on it. Read the "
            "individual tests below before relying on the published volume.")

# ---------- dashboard ----------
def badge(v):
    col = {"supported": GOOD, "contradicted": BAD, "inconclusive": WARN}.get(v, MUTE)
    return f'<span class="badge" style="background:{col}">{e(v)}</span>'


def test_card(tid):
    v = V[tid]
    if v["rule"] == "between":
        rule = f"pass if between {v['low']}× and {v['high']}×"
        val = ratio(v["value"])
        rule += f" · 95% CI {ratio(v['lo'])} to {ratio(v['hi'])}"
    elif tid == "T6":
        rule = f"pass if above {v['threshold']} bps"
        val = bps(v["value"])
    else:
        rule = f"pass if {v['rule']} {pct(v['threshold'], 0)} · 95% CI {pct(v['lo'])} to {pct(v['hi'])}"
        val = pct(v["value"])
    if v.get("repl"):
        f_ = ratio if tid == "T1" else pct
        rule += f" · main {f_(v['main_val'][0])}, replication {f_(REPL[tid][0])}"
    return (f'<div class="card"><div class="cardtop"><b>{tid}</b>{badge(v["verdict"])}</div>'
            f'<div class="claim">{e(v["claim"])}</div><div class="big">{e(val)}</div>'
            f'<div class="rule">{e(rule)}</div></div>')


def acct_rows(rows):
    out = []
    for r in rows[:8]:
        out.append([f'<code title="{e(r["account"])}">{e(short(r["account"]))}</code>', e(r["type"]),
                    e(ci(r["share"])), pct(r["window_share"], 0), num(r["counterparties"])])
    return out



VCOL = {"supported": GOOD, "contradicted": BAD, "inconclusive": WARN, "no data": MUTE}


def rob_cell(tid, r):
    v = r.get(tid)
    if tid == "T1" and r["name"] == "Whales removed":
        return '<span class="muted">not meaningful</span>'
    if v is None:
        return '<span class="muted">n/a</span>'
    f = ratio if tid == "T1" else (lambda x: pct(x, 0))
    verdict = judge(TBY[tid], v)[0] if tid in TBY else ""
    dot = f'<span class="dot" style="background:{VCOL.get(verdict, MUTE)}" title="{e(verdict)}"></span>' if verdict else ""
    extra = f" <span class='muted'>{e(cn(r['T2_chain']))}</span>" if tid == "T2" else ""
    return f"{dot}<b>{e(f(v[0]))}</b> <span class='muted'>({e(f(v[1]))}–{e(f(v[2]))})</span>{extra}"


rob_tbl = table(["Run", "Windows", "T1 deposits ÷ published", "T2 top chain", "T3 stablecoins", "T4 top sender",
                 "T5 top-5 signers", "Treasury, either side", "Shielded share"],
                [[f'<b>{e(r["name"])}</b><br><span class="muted small">{e(r["what"])}</span>', num(r["windows"])] +
                 [rob_cell(t, r) for t in ("T1", "T2", "T3", "T4", "T5", "router", "shield_vs_public")] for r in ROB])
main_v = {t: judge(TBY[t], ROB[0].get(t))[0] for t in ("T1", "T2", "T3", "T4", "T5")} if ROB else {}
flips = []
for r in ROB[1:]:
    for t in ("T1", "T2", "T3", "T4", "T5"):
        if t == "T1" and r["name"] == "Whales removed":
            continue
        if r.get(t) is None:
            continue
        v2 = judge(TBY[t], r[t])[0]
        if v2 != main_v[t]:
            flips.append(f"{t} is {v2} in “{r['name']}” ({main_v[t]} in the main sample)")
HOLD = [t for t in ("T1", "T2", "T3", "T4", "T5") if not any(f_.startswith(t + " ") for f_ in flips)]
n_checks = sum(1 for r in ROB[1:] for t in ("T1", "T2", "T3", "T4", "T5")
               if r.get(t) is not None and not (t == "T1" and r["name"] == "Whales removed"))
ROB_SAY = (f"{n_checks - len(flips)} of {n_checks} re-checks give the same verdict as the main sample. " +
           ("No verdict flips to the opposite side. " if not any("contradicted" in f_ and "supported" in f_ for f_ in flips) else "") +
           ("Differences: " + "; ".join(flips) + ". " if flips else "Every verdict holds in every run. ") +
           (f"{join(HOLD)} {'gives' if len(HOLD) == 1 else 'give'} the same verdict in every run, and the treasury's share is between "
            f"{pct(min(r['router'][0] for r in ROB), 0)} and {pct(max(r['router'][0] for r in ROB), 0)} in every run. " if HOLD else "") +
           "T2 and T4 depend on a few very large deposits and transfers, so the headline marks them inconclusive.")

daily = N["daily"]
dl = [r["date"] for r in daily]
chart_recon = lines([("published volume", C2, [r["llama_volume"] for r in daily]),
                     ("deposits (sample)", C1, [r["deposit_usd"] for r in daily]),
                     ("withdrawals (sample)", C3, [r["withdraw_usd"] for r in daily])], dl) if daily else ""
chart_tx = lines([("sample estimate", C1, [r["tx"] for r in daily]),
                  ("exact count", C2, [r.get("exact_tx") for r in daily])], dl, fmt=lambda x, d=0: f"{x / 1e3:.0f}K") if daily else ""
chart_send = hbars([(short(r["account"]), *r["share"], r["account"]) for r in LED["senders"][:8]], color=C2)
chart_recv = hbars([(short(r["account"]), *r["share"], r["account"]) for r in LED["receivers"][:8]], color=C1)
chart_diff = hbars([(short(r["account"]), *r["share"], r["account"]) for r in LED["token_diff_accounts"][:8]], color=C3)
ref_tbl = table(["Referral tag", "Events in sample", "Share of tagged value"],
                [[f"<code>{e(r['tag'][:34])}</code>", num(r["events"]), e(ci(r["share"]))] for r in N["referrals"][:7]])
chart_shield = lines([("published volume", C2, [r["llama_volume"] for r in daily]),
                      ("shielded into Confidential Intents (sample)", C3, [r.get("shield_usd") for r in daily])], dl) if daily else ""
chart_dep = hbars([(cn(r["chain"]), *r["share"], r["chain"]) for r in CH["deposits"][:10]], color=C1)
chart_wd = hbars([(cn(r["chain"]), *r["share"], r["chain"]) for r in CH["withdrawals"][:10]], color=C3)
chart_asset = hbars([(r["symbol"], *r["share"], r["symbol"]) for r in AS["top"][:8]], color=C1)
chart_sign = hbars([(short(r["signer"]), *r["share"], r["signer"]) for r in AC["signers"][:7]], color=C2)
mon = [m for m in N["monthly"] if m["volume"] > 0][-18:]
chart_month = cols([m["month"][2:] for m in mon], [m["volume"] for m in mon],
                   line=[m["rev_bps"] for m in mon], line_fmt=lambda x: f"{x:.0f}bp", line_name="NEAR revenue, bps of volume")
dp = N["daily_public"]
chart_px = lines([("Intents volume, 7-day mean", C1, [
    (sum(x[1] or 0 for x in dp[max(0, i - 6):i + 1]) / len(dp[max(0, i - 6):i + 1])) for i in range(len(dp))])],
    [x[0] for x in dp], right=("NEAR price", C2, [x[2] for x in dp]), right_fmt=lambda x, d=0: f"${x:.1f}")
LEAD = N.get("lead") or {}

stand_tbl = table(["Account", "Type", "Received (sample)", "Sent (sample)", "Seen in % of windows", "Counterparties"],
                  [[f'<code title="{e(r["account"])}">{e(short(r["account"]))}</code>' + (f' <b>{e(KNOWN[r["account"]]["label"])}</b>' if r["account"] in KNOWN else ""), e(r["type"]), usd(r["received"]),
                    usd(r["sent"]), pct(r["window_share"], 0), num(r["counterparties"])] for r in ST["accounts"][:10]])
lead_tbl = ""
if LEAD:
    lead_tbl = table(["Daily change in intents.near transactions vs…", "same day", "previous day", "levels"],
                     [["Intents volume (published)", r2(LEAD["corr_tx_vs_volume_same_day"]), r2(LEAD["corr_tx_vs_volume_prev_day"]), r2(LEAD["corr_levels_tx_volume"])],
                      ["NEAR price", r2(LEAD["corr_tx_vs_price_same_day"]), r2(LEAD["corr_tx_vs_price_prev_day"]), r2(LEAD["corr_levels_tx_price"])]])

fetched = dt.datetime.fromtimestamp(PUB["fetched_at"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
CSS = f"""
*{{box-sizing:border-box}}body{{margin:0;background:{BG};color:{INK};font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 20px 80px}}
h1{{font:700 34px/1.12 Georgia,"Times New Roman",serif;margin:6px 0 10px;letter-spacing:-.01em}}
h2{{font:700 22px/1.2 Georgia,serif;margin:44px 0 6px;padding-top:18px;border-top:2px solid {INK}}}
h3{{font-size:14px;margin:0 0 6px;text-transform:uppercase;letter-spacing:.06em;color:{MUTE}}}
.kick{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:{C1};font-weight:700}}
.lede{{font-size:17px;max-width:820px}}.muted{{color:{MUTE}}}.small{{font-size:12.5px}}
.grid{{display:grid;gap:14px}}.g3{{grid-template-columns:repeat(3,1fr)}}.g2{{grid-template-columns:repeat(2,1fr)}}
@media(max-width:820px){{.g3,.g2{{grid-template-columns:1fr}}h1{{font-size:27px}}}}
.card,.panel{{background:#fff;border:1px solid {LINE};border-radius:10px;padding:14px 16px}}
.cardtop{{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:{MUTE}}}
.claim{{font-size:13.5px;min-height:58px;margin-top:6px}}.big{{font:700 30px/1.1 Georgia,serif;margin:6px 0 2px}}
.rule{{font-size:11.5px;color:{MUTE}}}.badge{{color:#fff;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:99px;text-transform:uppercase;letter-spacing:.05em}}
.view{{background:{INK};color:#fff;border-radius:12px;padding:20px 22px;margin:22px 0;font-size:16.5px}}
.view b{{color:#a7f3d0}}.chart{{width:100%;height:auto;display:block}}
.say{{font-size:14px;margin:8px 0 0}}.say b{{font-weight:650}}
.tw{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid {LINE};white-space:nowrap}}
th{{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:{MUTE}}}code{{font:12px ui-monospace,Menlo,Consolas,monospace;background:#f3f4f6;padding:1px 5px;border-radius:4px}}
.facts{{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:13px;color:{MUTE};margin:14px 0 4px}}.facts b{{color:{INK}}}
details{{margin-top:8px}}summary{{cursor:pointer;color:{C3};font-size:13px}}pre{{background:#111827;color:#e5e7eb;padding:12px;border-radius:8px;overflow-x:auto;font-size:12px}}
ul{{padding-left:20px}}.live{{border:1px solid {LINE};border-radius:12px;padding:12px 16px;margin:14px 0;background:#fff}}.livehead{{margin-bottom:8px}}.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;background:{WARN};margin-right:6px}}.livegrid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}.lk{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:{MUTE}}}.lv{{font-size:20px;font-weight:650}}@media(max-width:820px){{.livegrid{{grid-template-columns:repeat(2,1fr)}}}}.hl{{display:block;text-decoration:none;color:{INK};background:#fff;border:1px solid {LINE};border-left:5px solid {C2};border-radius:12px;padding:16px 20px;margin:16px 0}}
.hl:hover{{border-color:{C2}}}.hlk{{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:{C2};font-weight:700}}.hlt{{font:700 22px/1.2 Georgia,serif;margin:4px 0 12px}}
.hlg{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.hln{{font:700 26px/1.1 Georgia,serif}}.hls{{font-size:13px;color:{MUTE};margin-top:4px}}
.nav{{position:sticky;top:0;z-index:5;background:{BG};border-bottom:1px solid {LINE};margin:0 -20px;padding:8px 20px;display:flex;gap:4px 14px;flex-wrap:wrap;font-size:12.5px}}
.nav a{{color:{MUTE};text-decoration:none;white-space:nowrap}}.nav a:hover,.nav a.on{{color:{INK};font-weight:650}}h2{{scroll-margin-top:64px}}
.wrapc td{{white-space:normal;vertical-align:top}}.wrapc code{{white-space:normal;word-break:break-all}}.grid>*{{min-width:0}}a{{color:{C3}}}
@media(max-width:820px){{.hlg{{grid-template-columns:1fr}}.nav{{flex-wrap:nowrap;overflow-x:auto}}}}
@media print{{.nav,.live,#sl{{display:none}}details{{display:none}}.panel,.card{{break-inside:avoid}}body{{background:#fff}}}}
.slrow{{display:grid;grid-template-columns:1fr 330px;gap:14px;align-items:center;padding:10px 0;border-bottom:1px solid {LINE}}}.slrow input{{width:150px;vertical-align:middle}}.thv{{font-size:12px;color:{MUTE};margin:0 6px}}@media(max-width:820px){{.slrow{{grid-template-columns:1fr}}}}.rob table{{font-size:12px}}.rob td,.rob th{{padding:6px 5px}}.rob td:first-child{{white-space:normal;min-width:150px}}.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}}td br+span{{white-space:normal}}li{{margin:4px 0}}
"""


def panel(title, chart, say, src):
    return (f'<div class="panel"><h3>{e(title)}</h3>{chart}<p class="say">{say}</p>'
            f'<details><summary>How this is computed</summary><p class="small muted">{src}</p></details></div>')


SW = N.get("switch")
SW_TXT = SW_NOW = ""
chart_switch = chart_pubshield = ""
if SW:
    _b, _a = SW["before"], SW["after"]
    _low = [r for r in daily if r["swap_tx_share"] < 0.03]
    _run = []
    for r in reversed(daily):
        if r["swap_tx_share"] < 0.03:
            _run.append(r)
        else:
            break
    _run.reverse()
    SW_TXT = (f"Up to {_b['to']}, {ci(_b['swap_tx_share'])} of transactions carried a swap settled in the open. "
              f"From {_a['from']} it is {ci(_a['swap_tx_share'])}. Open swaps fell from about {usd(_b['public_swap_usd_per_day'][0], 0)} to "
              f"{usd(_a['public_swap_usd_per_day'][0], 0)} a day while shielded value rose from {usd(_b['shield_usd_per_day'][0], 0)} to "
              f"{usd(_a['shield_usd_per_day'][0], 0)} a day.")
    if len(_run) >= 3:
        SW_NOW = (f" The share has been under 3% on every one of the last {len(_run)} full days (since {_run[0]['date']}), "
                  f"with open swaps averaging {usd(sum(r['public_swap_usd'] for r in _run) / len(_run), 0)} a day.")
    SW_PUB = (f"Published volume did not fall with it: {usd(_b['published_volume_per_day'], 0)} a day before, {usd(_a['published_volume_per_day'], 0)} after. "
              f"Swaps we can see in the open were {pct(_b['public_swap_over_published'], 0)} of the published figure before the break and "
              f"{pct(_a['public_swap_over_published'], 0)} after. The rest of the published number now has to be taken on trust.")
    _bb = SW.get("break_date_bootstrap")
    SW_UNC = (f" Re-drawing the sample {num(_bb['draws'])} times puts the break between {_bb['range_95'][0]} and {_bb['range_95'][1]} in 95% of draws."
              if _bb else "")
    chart_switch = lines([("share of transactions with an open swap", C1, [r["swap_tx_share"] for r in daily])], dl, fmt=pct)
    chart_pubshield = lines([("swaps settled in the open", C1, [r["public_swap_usd"] for r in daily]),
                             ("shielded into Confidential Intents", C3, [r["shield_usd"] for r in daily])], dl)

TB = None
_tb = os.path.join(ROOT, "data", "public", "treasury_balance.json")
if os.path.exists(_tb):
    TB = json.load(open(_tb))
    TB_WHEN = dt.datetime.fromtimestamp(TB["fetched_at"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    _sh = (SW["after"]["shield_usd_per_day"][0] if SW else CF["shield_usd_per_day"][0])
    TB_TXT = (f"At block {num(TB['block_height'])} ({TB_WHEN}) the treasury held {usd(TB['total_usd'], 0)} on the public contract, in {TB['assets_held']} assets; "
              f"{pct(TB['stable_usd'] / TB['total_usd'], 0)} of it stablecoins. About {usd(_sh, 0)} a day has been shielded since the break, "
              f"so the pool turns over roughly every {TB['total_usd'] / _sh:.1f} days.")
    chart_tb = hbars([(f"{r['symbol']} ({cn(r['chain'])})", r["usd"] / TB["total_usd"], r["usd"] / TB["total_usd"], r["usd"] / TB["total_usd"], r["asset"]) for r in TB["rows"][:8]], color=C3)

SHD = CF.get("shielders")
if SHD:
    _named = [r for r in SHD["top"] if r["type"] == "named"]
    SHD_TXT = (f"{num(SHD['distinct_in_sample'])} different accounts shielded funds in the sampled windows. "
               + (f"Two solver accounts, {_named[0]['account']} and {_named[1]['account']}, supply {pct(_named[0]['share'][0] + _named[1]['share'][0], 0)} of the shielded value between them; "
                  if len(_named) >= 2 else "")
               + f"the ten largest shielders together account for {ci(SHD['top10_share'])}. "
               f"Accounts that each contribute under 1% make up {pct(SHD['accounts_under_1pct_share'], 0)}. So use is broad by count, with solver liquidity as the largest single block.")
    chart_shd = hbars([(short(r["account"]), *r["share"], r["account"]) for r in SHD["top"][:6]], color=C3)

def _load(name):
    p_ = os.path.join(ROOT, "data", "public", name)
    return json.load(open(p_)) if os.path.exists(p_) else None


PEER, MKT, TIM = _load("peers.json"), _load("market.json"), N.get("timing")
PEER_HTML = PEER_TXT = VAL_HTML = TIME_HTML = FLOW_HTML = THIRD_TXT = TAKE_TXT = ""
if PEER:
    _rows = PEER["rows"]
    for r in _rows:
        r["take"] = r["revenue_30d"] / r["volume_30d"] * 1e4 if r.get("volume_30d") and r.get("revenue_30d") is not None else None
        r["cost"] = r["fees_30d"] / r["volume_30d"] * 1e4 if r.get("volume_30d") and r.get("fees_30d") is not None else None
    _me = next(r for r in _rows if r["slug"] == "near-intents")
    _cmp = sorted([r for r in _rows if r["take"] is not None], key=lambda r: -r["take"])
    _big = [r for r in _cmp if r["slug"] != "near-intents" and r["volume_30d"] >= 0.1 * _me["volume_30d"]]
    _byrev = sorted([r for r in _rows if r.get("revenue_30d") is not None], key=lambda r: -r["revenue_30d"])
    PEER_HTML = table(["Venue", "Volume", "Users pay", "Keeps", "Take", "Revenue"],
                      [[("<b>" + e(r["name"]) + "</b>") if r is _me else e(r["name"]), usd(r["volume_30d"], 2) if r.get("volume_30d") else '<span class="muted">no series</span>',
                        bps(r["cost"]) if r["cost"] is not None else "n/a", bps(r["take"]) if r["take"] is not None else "n/a",
                        "", usd(r["revenue_30d"], 2) if r.get("revenue_30d") is not None else "n/a"] for r in sorted(_rows, key=lambda r: -(r.get("revenue_30d") or 0))], "small")
    PEER_HTML = PEER_HTML.replace("<th>Take</th>", "").replace("<td></td>", "")
    PEER_TXT = (f"DefiLlama has both volume and revenue for {len(_cmp)} of these {len(_rows)} venues. Among them NEAR Intents keeps {bps(_me['take'])}, "
                f"ranking {_cmp.index(_me) + 1} of {len(_cmp)}. "
                + (f"The venues of comparable size keep less: {join([r['name'] + ' ' + bps(r['take']) for r in _big])}. " if _big and all(r["take"] < _me["take"] for r in _big) else "")
                + (f"By revenue in dollars it is first of the {len(_byrev)}. " if _byrev[0] is _me else f"By revenue in dollars it ranks {_byrev.index(_me) + 1} of {len(_byrev)}. ")
                + ("This cuts against our own T6 objection: the 5 bps bar was ours, and the comparable venues we can measure do not clear it either."
                   if _big and all(r["take"] < 5 for r in _big) else ""))
if MKT:
    _ann = PUB["annualised_revenue"]
    VAL_HTML = f"""<div class="panel"><h3>What today's price asks of Intents</h3>
<p class="say">NEAR's market value is {usd(MKT['market_cap'], 2)} ({dt.datetime.fromtimestamp(MKT['fetched_at'], dt.timezone.utc).strftime('%Y-%m-%d')}). Intents revenue annualises to {usd(_ann, 1)}, so the token trades at <b>{MKT['market_cap'] / _ann:.0f}×</b> that revenue. Pick the multiple you think is fair and see what Intents would have to deliver for revenue alone to justify the price.</p>
<div style="margin:10px 0"><input type="range" id="vm" min="10" max="100" step="5" value="30" style="width:220px;vertical-align:middle" aria-label="revenue multiple"> <b id="vmv"></b></div>
<div class="livegrid" style="grid-template-columns:repeat(3,1fr)" id="vg"></div>
<p class="small muted" style="margin-top:8px">Arithmetic, not a forecast. It isolates Intents revenue and ignores everything else the token is valued for (gas, staking, other protocols), so it overstates what Intents alone must do. Market value from CoinGecko; revenue and volume from DefiLlama, last 30 days.</p></div>
<script>(function(){{const M={MKT['market_cap']},R={_ann},V={PUB['volume_30d'] / 30},B={PUB['rev_bps_30d']};
const u=v=>v>=1e9?"$"+(v/1e9).toFixed(2)+"B":"$"+(v/1e6).toFixed(0)+"M",s=document.getElementById("vm"),g=document.getElementById("vg"),l=document.getElementById("vmv");
function f(){{const m=+s.value,need=M/m,x=need/R;l.textContent=m+"× revenue";
g.innerHTML=`<div><div class="lk">Revenue needed</div><div class="lv">${{u(need)}} a year</div><span class="muted small">${{x.toFixed(1)}}× today's</span></div>`+
`<div><div class="lk">Take needed at today's volume</div><div class="lv">${{(B*x).toFixed(0)}} bps</div><span class="muted small">today ${{B.toFixed(1)}} bps</span></div>`+
`<div><div class="lk">Volume needed at today's take</div><div class="lv">${{u(V*x)}} a day</div><span class="muted small">today ${{u(V)}}</span></div>`;}}
s.addEventListener("input",f);f();}})();</script>"""
if TIM:
    _h = TIM["by_utc_hour"]
    _best = max(range(24), key=lambda i: sum(_h[(i + j) % 24] for j in range(8)))
    _wk = TIM["by_weekday_mon0"][5] + TIM["by_weekday_mon0"][6]
    _wkexp = sum(1 for r in daily if dt.date.fromisoformat(r["date"]).weekday() >= 5) / max(1, len(daily))
    chart_time = lines([("share of sampled transactions", C1, _h)], [f"{h:02d}h" for h in range(24)], fmt=lambda v, *_: pct(v, 1))
    TIME_HTML = panel("When it is used (UTC hour)", chart_time,
                      f"The busiest eight hours, {_best:02d}:00 to {(_best + 8) % 24:02d}:00 UTC, carry {pct(sum(_h[(_best + j) % 24] for j in range(8)), 0)} of transactions; an even spread would be 33%. "
                      f"Weekends carry {pct(_wk, 0)}, against {pct(_wkexp, 0)} if every day in the sample were equal. " +
                      "The hour-by-hour line is noisy, so only the broad tilt is worth reading.",
                      "Each sampled transaction is counted in the UTC hour of its block. Every window carries the same weight, so plain shares are unbiased for the period.")
TIME_WHY = ""
if TIM:
    TIME_WHY = (f"Transactions lean a little towards {_best:02d}:00–{(_best + 8) % 24:02d}:00 UTC and away from weekends. Software alone would not slow down at weekends, so this hints at people behind the five relayers. "
                f"It is a weak hint: each hour rests on about {G['windows_used'] // 24} windows, single busy windows move the line, and the end users never appear as the signer here.")
_dps, _wds = {r["chain"]: r["share"][0] * TPD["deposit_usd"][0] for r in CH["deposits"]}, {r["chain"]: r["share"][0] * TPD["withdraw_usd"][0] for r in CH["withdrawals"]}
_chs = sorted(set(_dps) | set(_wds), key=lambda c: -(abs(_dps.get(c, 0) - _wds.get(c, 0))))[:8]
if _chs:
    _src, _snk = max(_chs, key=lambda c: _dps.get(c, 0) - _wds.get(c, 0)), min(_chs, key=lambda c: _dps.get(c, 0) - _wds.get(c, 0))
    FLOW_HTML = ('<div class="panel" style="margin-top:14px"><h3>Net flow by chain: where value enters and where it leaves</h3>' +
                 table(["Chain", "Deposited / day", "Withdrawn / day", "Net / day", "Role"],
                       [[e(cn(c)), usd(_dps.get(c, 0), 0), usd(_wds.get(c, 0), 0), ("+" if _dps.get(c, 0) >= _wds.get(c, 0) else "−") + usd(abs(_dps.get(c, 0) - _wds.get(c, 0)), 0),
                         "source" if _dps.get(c, 0) > _wds.get(c, 0) else "sink"] for c in _chs], "small") +
                 f'<p class="say">{e(cn(_src))} is the largest net source and {e(cn(_snk))} the largest net sink in the main sample. These are point estimates from chain shares that carry wide intervals (see the two charts above), so read the direction, not the dollar figure. Deposits and withdrawals do not have to balance: value can stay inside the ledger, including in shielded balances.</p></div>')
_third = next((r for r in ROB if r["name"] == "Third sample"), None)
_p3 = next((r for r in ROB if r["name"] == "Pooled (all three samples)"), None)
if _third:
    _tv = {t: judge(TBY[t], _third[t])[0] for t in ("T1", "T2", "T3", "T4", "T5") if _third.get(t)}
    _agree = [t for t in _tv if _tv[t] == V[t]["verdict"]]
    _opp = [t for t in _tv if {_tv[t], V[t]["verdict"]} == {"supported", "contradicted"}]
    THIRD_TXT = (f" A third sample ({num(_third['windows'])} windows, {num(_third['transactions'])} transactions) was drawn after the verdict rule was fixed, so it is an out-of-sample check. "
                 f"On its own it gives {join([t + ' ' + _tv[t] for t in _tv])}: the same as the headline for {len(_agree)} of {len(_tv)} tests"
                 + (", and the opposite for " + join(_opp) + "." if _opp else ", and the opposite verdict for none.") + " The headline verdicts were not changed after seeing it."
                 + (f" Pooling all three samples gives T1 {ci(_p3['T1'], ratio)}, against {ci(POOL['T1'], ratio)} for the first two: still inside the 0.5×–2× band, but nearer its lower edge. All three samples put deposits below the published volume."
                    if _p3 and _p3.get("T1") and POOL and 0.5 < _p3["T1"][1] and _p3["T1"][0] < POOL["T1"][0] and all(r["T1"][0] < 1 for r in (ROB[0], REPL, _third)) else ""))
if SW and SW["before"].get("rev_bps") is not None:
    TAKE_TXT = (f"NEAR's take was {bps(SW['before']['rev_bps'])} of published volume before the break and {bps(SW['after']['rev_bps'])} after; what users paid went from "
                f"{bps(SW['before']['fee_bps'])} to {bps(SW['after']['fee_bps'])}. The timing matches; we have no evidence of cause.")

LONG = _load("intents_tx_counts_long.json")
LONG_HTML = LONG_TXT = ""
if LONG and len(LONG["rows"]) >= 90:
    _lr = [r for r in LONG["rows"] if r[1]]
    _ld = [dt.datetime.fromtimestamp(r[0], dt.timezone.utc).strftime("%Y-%m-%d") for r in _lr]
    _lv = {d: v for d, v, _ in N["daily_public"]}
    _first, _last = _lr[:30], _lr[-30:]
    _a1, _a2 = sum(r[1] for r in _first) / len(_first), sum(r[1] for r in _last) / len(_last)
    _v1 = [_lv.get(d) for d in _ld[:30] if _lv.get(d)]
    _v2 = [_lv.get(d) for d in _ld[-30:] if _lv.get(d)]
    LONG_TXT = (f"Exact counts for {len(_lr)} days. The contract handled about {num(_a1)} transactions a day in the first 30 days of this window ({_ld[0]} onwards) "
                f"and {num(_a2)} a day in the last 30: {_a2 / _a1:.1f}× as many. "
                + (f"Published volume over the same two spans went from {usd(sum(_v1) / len(_v1), 0)} to {usd(sum(_v2) / len(_v2), 0)} a day ({(sum(_v2) / len(_v2)) / (sum(_v1) / len(_v1)):.1f}×). " if _v1 and _v2 else "")
                + f"The busiest day was {_ld[max(range(len(_lr)), key=lambda i: _lr[i][1])]} with {num(max(r[1] for r in _lr))} transactions.")
    chart_long = lines([("transactions touching intents.near per day (exact)", C1, [r[1] for r in _lr])], [d[5:] for d in _ld], fmt=lambda v, *_: num(v),
                       right=("published volume", C2, [_lv.get(d) for d in _ld]), right_fmt=usd)
    LONG_HTML = ('<div style="margin-top:14px">' + panel(f"Six months of usage: exact daily transactions, {len(_lr)} days", chart_long, e(LONG_TXT),
                 "The FastNEAR transactions API returns the exact number of transactions touching an account for any block range. We located the first block of each UTC day and asked for the count between consecutive days (<code>scripts/fetch_long_counts.py</code>). This is a full count, not a sample. Published volume is DefiLlama's daily series.") + "</div>")

FLOW_SVG = f"""<svg viewBox="0 0 1040 250" role="img" class="chart" aria-label="How a swap moves through NEAR Intents">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="{MUTE}"/></marker></defs>
<g font-family="ui-sans-serif,system-ui,sans-serif" font-size="12" fill="{INK}">
<rect x="10" y="90" width="130" height="56" rx="8" fill="#fff" stroke="{LINE}"/><text x="75" y="114" text-anchor="middle" font-weight="700">User</text><text x="75" y="131" text-anchor="middle" fill="{MUTE}" font-size="11">on another chain</text>
<rect x="230" y="70" width="250" height="96" rx="8" fill="#fff" stroke="{INK}" stroke-width="1.5"/><text x="355" y="96" text-anchor="middle" font-weight="700">intents.near (public ledger)</text><text x="355" y="116" text-anchor="middle" fill="{MUTE}" font-size="11">open swap: dip4:token_diff</text><text x="355" y="133" text-anchor="middle" fill="{MUTE}" font-size="11">everything here is readable</text><text x="355" y="150" text-anchor="middle" fill="{MUTE}" font-size="11">and is what this project samples</text>
<rect x="580" y="90" width="170" height="56" rx="8" fill="#fff" stroke="{C3}" stroke-width="1.5"/><text x="665" y="114" text-anchor="middle" font-weight="700">Confidential treasury</text><text x="665" y="131" text-anchor="middle" fill="{MUTE}" font-size="11">holds the public tokens</text>
<rect x="850" y="90" width="180" height="56" rx="8" fill="#f3f4f6" stroke="{MUTE}" stroke-dasharray="5 4"/><text x="940" y="114" text-anchor="middle" font-weight="700">intents.far (private)</text><text x="940" y="131" text-anchor="middle" fill="{MUTE}" font-size="11">swap not visible outside</text>
<rect x="270" y="200" width="170" height="40" rx="8" fill="#fff" stroke="{C2}"/><text x="355" y="225" text-anchor="middle" font-weight="700">Relayer accounts</text>
<rect x="10" y="10" width="130" height="40" rx="8" fill="#fff" stroke="{LINE}"/><text x="75" y="35" text-anchor="middle" font-weight="700">Destination chain</text>
<line x1="140" y1="118" x2="228" y2="118" stroke="{MUTE}" marker-end="url(#ar)"/><text x="184" y="110" text-anchor="middle" font-size="10.5" fill="{MUTE}">deposit</text><text x="184" y="134" text-anchor="middle" font-size="10.5" fill="{MUTE}">mt_mint</text>
<line x1="480" y1="106" x2="578" y2="106" stroke="{MUTE}" marker-end="url(#ar)"/><text x="529" y="98" text-anchor="middle" font-size="10.5" fill="{MUTE}">shield</text>
<line x1="580" y1="132" x2="482" y2="132" stroke="{MUTE}" marker-end="url(#ar)"/><text x="529" y="148" text-anchor="middle" font-size="10.5" fill="{MUTE}">unshield</text>
<line x1="750" y1="118" x2="848" y2="118" stroke="{MUTE}" stroke-dasharray="5 4" marker-end="url(#ar)"/><text x="799" y="110" text-anchor="middle" font-size="10.5" fill="{MUTE}">backs 1:1</text>
<line x1="355" y1="200" x2="355" y2="168" stroke="{MUTE}" marker-end="url(#ar)"/><text x="364" y="188" font-size="10.5" fill="{MUTE}">sign and submit</text>
<path d="M300 70 L300 30 L142 30" fill="none" stroke="{MUTE}" marker-end="url(#ar)"/><text x="222" y="24" text-anchor="middle" font-size="10.5" fill="{MUTE}">withdrawal: mt_burn</text>
</g></svg>"""
_GLOSS = [("Intent", "A signed statement of the outcome a user wants, such as “at least X of token B for Y of token A”."),
          ("Solver", "A market maker that fills intents from its own inventory."),
          ("Relayer / signer", "The account that submits a transaction and pays the network fee. Test T5 measures how few of them there are."),
          ("Shield / unshield", "Moving funds into or out of the confidential side through the treasury account."),
          ("Open swap", "A swap settled on the public contract (a token_diff event), where anyone can see who gave what for what."),
          ("Basis point (bps)", "One hundredth of a percent. 5 bps of $100 is 5 cents."),
          ("Take", "The share of volume a protocol keeps as revenue."),
          ("Window / stratum", "The period is cut into equal strata; from each, one window of 40 consecutive blocks is downloaded in full."),
          ("95% interval", "The range holding the middle 95% of results when the sample is re-drawn from itself 2,000 times."),
          ("Pooled", "A precision-weighted average of independent samples."),
          ("Out-of-sample", "Checked on data that did not exist when the rule was written.")]
_SRC = [("FastNEAR transactions API", "tx.main.fastnear.com/v0", "Sampled transactions; exact daily counts"),
        ("NEAR RPC view call", "mt_batch_balance_of on intents.near", "Treasury holdings"),
        ("1Click token list", "1click.chaindefuser.com/v0/tokens", "Asset ids, chains, decimals, list prices"),
        ("DefiLlama", "api.llama.fi, coins.llama.fi", "Published volume, fees, revenue; daily prices; peers"),
        ("CoinGecko", "api.coingecko.com/api/v3/coins/near", "NEAR market value"),
        ("NEAR Intents documentation", "docs.near-intents.org/integration/market-makers/confidential-example", "Treasury account, private contract, shield and unshield"),
        ("BigQuery public dataset", "bigquery-public-data.crypto_near_mainnet_us", "Cross-check queries in sql/ (written, not run)")]
GLOSS_TBL = table(["Term", "Meaning"], [[f"<b>{e(a_)}</b>", e(b_)] for a_, b_ in _GLOSS], "small wrapc")
SRC_TBL = table(["Source", "Where", "Used for"], [[e(a_), f"<code>{e(b_)}</code>", e(c_)] for a_, b_, c_ in _SRC], "small wrapc")

PRED = json.load(open(os.path.join(ROOT, "predictions.json"))) if os.path.exists(os.path.join(ROOT, "predictions.json")) else None


def _met(p, v):
    v = v[0] if isinstance(v, list) else v
    if v is None:
        return None
    return {"at_least": v >= p["threshold"], "above": v > p["threshold"], "below": v < p["threshold"]}[p["rule"]]


def _pv(p, v):
    v = v[0] if isinstance(v, list) else v
    return "n/a" if v is None else {"share": pct, "bps": bps, "usd": lambda x: usd(x, 0)}[p["kind"]](v)


TRK = []
_tp = os.path.join(ROOT, "data", "history", "tracker.jsonl")
if os.path.exists(_tp):
    TRK = [json.loads(l) for l in open(_tp) if l.strip()]


def _c(v, f=pct):
    return "n/a" if not v else f'{f(v[0])} <span class="muted small">({f(v[1])}–{f(v[2])})</span>'


if TRK:
    _snap = [["<b>Snapshot, pooled</b>", f"{G['first_day']} → {G['last_day']}", num(POOL["windows"]) if POOL else "", "",
              _c(POOL["T2"]) + f' {e(POOL.get("T2_chain", ""))}', _c(POOL["T3"]), _c(POOL["T4"]), _c(POOL["T5"]), _c(PSV),
              usd(CF["shield_usd_per_day"][0], 0), usd(CF["public_swap_usd_per_day"][0], 0), usd(PUB["volume_30d"] / 30, 0), bps(PUB["rev_bps_30d"])]] if POOL else []
    TRK_HTML = table(["Run", "Covers", "Windows", "Txs", "T2 top chain", "T3 stablecoins", "T4 top sender", "T5 top-5 signers",
                      "Shielded share", "Shielded / day", "Public swaps / day", "Published volume / day", "NEAR's take"],
                     _snap + [[e(r["date"]), "24 h to block " + num(r["end_height"]), num(r["windows"]), num(r["transactions"]),
                               _c(r["T2"]) + f' {e(r["T2_chain"])}', _c(r["T3"]), _c(r["T4"]), _c(r["T5"]), _c(r["shield_vs_public"]),
                               usd(r["shield_usd_per_day"][0], 0), usd(r["public_swap_usd_per_day"][0], 0), usd(r["published_volume_last_full_day"], 0) + f' <span class="muted small">({e(r["published_day"])})</span>',
                               bps(r["T6_bps_last_full_day"]) if r.get("T6_bps_last_full_day") else "n/a"] for r in TRK[-14:]], "small")
    _l = TRK[-1]
    if _l["shield_vs_public"][1] > PSV[2]:
        TRK_HTML += (f'<p><b>What the latest row adds.</b> On {e(_l["date"])} swaps settled in the open came to about {usd(_l["public_swap_usd_per_day"][0], 0)} a day, '
                     f'against {usd(CF["public_swap_usd_per_day"][0], 0)} a day averaged over the snapshot, while shielded value was {usd(_l["shield_usd_per_day"][0], 0)} a day. '
                     f'The shielded share for that day is {pct(_l["shield_vs_public"][0])}, above the whole snapshot interval. '
                     'So the 30-day average understates where things stand now: on this evidence nearly all swap value has moved to the confidential side.</p>')
    TRK_HTML += ('<p class="small muted">Tracker rows are valued at the 1Click price list fetched at run time. “Published volume / day” and “NEAR\'s take” in a tracker row are DefiLlama\'s last complete day; in the snapshot row they are 30-day figures. Each row can be re-drawn exactly from its seed and end block, stored in <code>data/history/tracker.jsonl</code>.</p>')
else:
    TRK_HTML = '<p class="muted">No tracker run yet. Run <code>python3 scripts/track.py</code> (about 10 minutes), or wait for the scheduled job.</p>'

PRED_HTML, PRED_ROWS = "", []
if PRED:
    base = next((r for r in TRK if r["date"] == PRED["registered"]), None)
    scored = [r for r in TRK if PRED["registered"] < r["date"] <= PRED["horizon"]]
    done = bool(scored) and dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d") > PRED["horizon"]
    for p_ in PRED["predictions"]:
        ms = [m for m in (_met(p_, r.get(p_["metric"])) for r in scored) if m is not None]
        hit = sum(ms)
        if not ms:
            st, col = "not scored yet", MUTE
        elif done:
            st, col = ("held", GOOD) if hit / len(ms) >= 0.8 else ("failed", BAD)
        else:
            st, col = ("on track", GOOD) if hit / len(ms) >= 0.8 else ("off track", BAD)
        PRED_ROWS.append({"id": p_["id"], "claim": p_["claim"], "pass": {"at_least": "≥ ", "above": "> ", "below": "< "}[p_["rule"]] + _pv(p_, p_["threshold"]),
                          "base": _pv(p_, base.get(p_["metric"])) if base else "n/a", "score": f"{hit} of {len(ms)} days", "status": st, "if_wrong": p_["if_wrong"]})
        PRED_ROWS[-1]["html"] = [f"<b>{p_['id']}</b>", e(p_["claim"]), PRED_ROWS[-1]["pass"], PRED_ROWS[-1]["base"], PRED_ROWS[-1]["score"],
                                 f'<span class="badge" style="background:{col}">{st}</span>', e(p_["if_wrong"])]
    PRED_HTML = (f'<h3 style="margin-top:22px">Five predictions, written down on {e(PRED["registered"])}, graded on {e(PRED["horizon"])}</h3>'
                 f'<p>A thesis should be able to lose. These are scored automatically from the tracker rows above; nobody edits the result by hand. {e(PRED["rule"])}</p>'
                 + table(["", "Prediction", "Met when", f"Baseline {PRED['registered']}", "Days met", "Status", "If we are wrong"], [r["html"] for r in PRED_ROWS], "small wrapc"))

import csv
CSVD = os.path.join(ROOT, "docs", "data")
os.makedirs(CSVD, exist_ok=True)
CSVS = []


def _csv(name, head, rows):
    with open(os.path.join(CSVD, name), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(head)
        w.writerows(rows)
    CSVS.append(name)


_r = lambda x, n=2: "" if x is None else round(x, n)
_csv("daily.csv", ["date", "windows", "tx_estimate", "tx_exact", "deposit_usd", "withdraw_usd", "transfer_usd", "shield_usd", "public_swap_usd", "open_swap_tx_share", "published_volume_usd"],
     [[r["date"], r["windows"], _r(r["tx"], 0), r.get("exact_tx") or "", _r(r["deposit_usd"]), _r(r["withdraw_usd"]), _r(r["transfer_usd"]), _r(r.get("shield_usd")),
       _r(r.get("public_swap_usd")), _r(r.get("swap_tx_share"), 5), _r(r["llama_volume"])] for r in daily])
_csv("tests.csv", ["test", "claim", "verdict", "pooled", "pooled_lo", "pooled_hi", "main", "replication"],
     [[t, V[t]["claim"], V[t]["verdict"]] + ([_r(x, 5) for x in POOL[t]] + [_r(ROB[0][t][0], 5), _r(REPL[t][0], 5)] if POOL and REPL and t in POOL else [""] * 5) for t in ("T1", "T2", "T3", "T4", "T5", "T6")])
_csv("robustness.csv", ["run", "windows", "transactions"] + [f"{t}{x}" for t in ("T1", "T2", "T3", "T4", "T5", "treasury_either_side", "shielded_share") for x in ("", "_lo", "_hi")],
     [[r["name"], r["windows"], r["transactions"]] + [_r(v, 5) for k in ("T1", "T2", "T3", "T4", "T5", "router", "shield_vs_public") for v in (r.get(k) or [None] * 3)] for r in ROB])
if TB:
    _csv("treasury.csv", ["asset", "symbol", "chain", "amount", "usd"], [[r["asset"], r["symbol"], r["chain"], r["amount"], _r(r["usd"])] for r in TB["rows"]])
if TRK:
    _k = ["date", "end_height", "windows", "transactions", "T2_chain", "published_volume_last_full_day", "T6_bps_30d"]
    _c3 = ["T2", "T3", "T4", "T5", "shield_vs_public", "shield_usd_per_day", "public_swap_usd_per_day"]
    _csv("tracker.csv", _k + [f"{c}{x}" for c in _c3 for x in ("", "_lo", "_hi")], [[r.get(k, "") for k in _k] + [_r(v, 5) for c in _c3 for v in r[c]] for r in TRK])

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEAR Intents X-Ray: an evidence-first investment thesis</title>
<meta name="description" content="A reproducible, sample-based audit of the NEAR Intents contract: six pre-registered tests, two independent samples, a daily tracker and dated predictions."><style>{CSS}</style></head><body><div class="wrap">
<div class="kick">NEAR Hackathon 2026 · Investment Thesis track</div>
<h1>NEAR Intents X-Ray: who is on the other side of {usd(PUB['volume_30d'] / 30, 0)} a day?</h1>
<p class="lede">Most NEAR theses quote one published volume number. This one opens the contract. We drew a seeded random sample of
<b>{num(G['windows_used'])} block windows</b> of <code>intents.near</code> across <b>{G['span_days']:.0f} days</b>, downloaded every transaction in them
(<b>{num(G['transactions'])}</b>), priced {pct(G['price_coverage'])} of the token legs, and tested six claims against thresholds fixed in advance.
Then we did it again: an independent second sample of <b>{num(REPL['windows']) if REPL else 0} windows</b> ({num(REPL['transactions']) if REPL else 0} transactions) with a different seed, to see which results survive.</p>
<p class="small" style="margin:10px 0 0"><b>Read it as a research note:</b> <a href="report.html">report.html</a> · <a href="NEAR-Intents-X-Ray-report.pdf">PDF, 12 pages</a> (takeaways, 15 exhibits, scenarios, risk register, questions for the team).</p>
<div class="facts"><span>Sample: <b>{e(G['first_day'])} → {e(G['last_day'])}</b></span><span>Each window stands for <b>{G['expansion_factor']:.0f}</b> windows</span>
<span>Intervals: <b>window bootstrap, {num(G['bootstrap_draws'])} draws</b></span><span>Public series fetched <b>{fetched}</b></span></div>
{f"""<a class="hl" href="#s2"><div class="hlk">Main finding</div>
<div class="hlt">In the last two weeks, swaps on NEAR Intents moved out of public view</div>
<div class="hlg"><div><div class="hln">{pct(SW['before']['swap_tx_share'][0], 0)} → {pct(SW['after']['swap_tx_share'][0], 1)}</div><div class="hls">of transactions carry a swap settled in the open (before and after {SW['first_day_after'][5:]})</div></div>
<div><div class="hln">{usd(SW['after']['shield_usd_per_day'][0], 0)} a day</div><div class="hls">now goes into Confidential Intents, where the swap itself cannot be audited from outside</div></div>
<div><div class="hln">{usd(TB['total_usd'], 0) if TB else 'n/a'}</div><div class="hls">held by the one treasury account that backs every shielded balance; the claims against it are not published</div></div></div></a>""" if SW else ""}
<div class="live" id="live"><div class="livehead"><span class="dot" id="ldot"></span><b>Live now</b> <span class="muted small" id="lstat">loading the public series from DefiLlama…</span></div>
<div class="livegrid" id="lgrid"></div>
<p class="small muted" style="margin:6px 0 0">Fetched by your browser each time this page opens. Everything below this strip is the frozen snapshot of {e(G['first_day'])} → {e(G['last_day'])}, which is what the verdicts and the rebuild command refer to.</p></div>
<script>
(function () {{
  const SNAP = {json.dumps({"vol30": PUB["volume_30d"], "bps": PUB["rev_bps_30d"], "px": PUB["near_price_last"], "th": TBY["T6"].get("threshold")})};
  const A = "https://api.llama.fi/summary/", get = u => fetch(u).then(r => {{ if (!r.ok) throw 0; return r.json(); }});
  const usd = v => v >= 1e9 ? "$" + (v / 1e9).toFixed(2) + "B" : v >= 1e6 ? "$" + (v / 1e6).toFixed(1) + "M" : "$" + Math.round(v).toLocaleString("en-US");
  const sum30 = c => c.slice(-31, -1).reduce((a, r) => a + r[1], 0);   // 30 complete days; the last row is today, partial
  const chg = (now, was) => {{ const d = (now / was - 1) * 100; return `<span class="muted small">${{d >= 0 ? "+" : ""}}${{d.toFixed(1)}}% vs snapshot</span>`; }};
  const stat = document.getElementById("lstat"), grid = document.getElementById("lgrid"), dot = document.getElementById("ldot");
  Promise.all([get(A + "dexs/near-intents"), get(A + "fees/near-intents?dataType=dailyRevenue"), get("https://coins.llama.fi/prices/current/coingecko:near")])
    .then(([v, r, p]) => {{
      const vc = v.totalDataChart, rc = r.totalDataChart, last = vc[vc.length - 2];
      const v30 = sum30(vc), r30 = sum30(rc), b = r30 / v30 * 1e4, px = p.coins["coingecko:near"].price;
      const day = new Date(last[0] * 1000).toISOString().slice(0, 10);
      const pass = b >= SNAP.th;
      const cell = (k, val, sub) => `<div><div class="lk">${{k}}</div><div class="lv">${{val}}</div>${{sub}}</div>`;
      grid.innerHTML =
        cell("Published volume, " + day, usd(last[1]), `<span class="muted small">last complete day</span>`) +
        cell("Published volume, 30 days", usd(v30), chg(v30, SNAP.vol30)) +
        cell("NEAR's take, 30 days", b.toFixed(1) + " bps", `<span class="muted small">snapshot ${{SNAP.bps.toFixed(1)}} bps</span>`) +
        cell("T6 on today's figures", `<span class="badge" style="background:${{pass ? "{GOOD}" : "{BAD}"}}">${{pass ? "supported" : "contradicted"}}</span>`, `<span class="muted small">pass if ≥ ${{SNAP.th}} bps</span>`) +
        cell("NEAR price", "$" + px.toFixed(2), chg(px, SNAP.px));
      stat.textContent = "updated " + new Date().toISOString().slice(0, 16).replace("T", " ") + " UTC · source: DefiLlama";
      dot.style.background = "{GOOD}";
    }})
    .catch(() => {{ stat.textContent = "could not reach DefiLlama (offline, or a sandboxed preview). The snapshot below is unaffected."; dot.style.background = "{MUTE}"; }});
}})();
</script>
<div class="view"><b>Investment view.</b> {e(VIEW)}</div>
<div class="grid g3">{''.join(test_card(t) for t in ('T1', 'T2', 'T3', 'T4', 'T5', 'T6'))}</div>
<p class="small muted">T1–T5 show the pooled estimate of two independent samples (1,080 windows). A test is “supported” or “contradicted” only when the whole pooled 95% interval is on one side of the threshold <b>and</b> both samples' own point estimates are on that side; otherwise it is “inconclusive”. Thresholds live in <code>thesis_tests.json</code>.</p>

<h2>1. Is the volume real?</h2><p>{e(T_TXT['T1'])}</p>
<div class="grid g2">
{panel("Daily value: published vs measured on-chain", chart_recon,
 f"Sample deposits average <b>{usd(TPD['deposit_usd'][0])}</b> a day (95% CI {usd(TPD['deposit_usd'][1])} to {usd(TPD['deposit_usd'][2])}) against <b>{usd(RC.get('published_volume_per_day'))}</b> published; withdrawals are {ci(RC['withdraw_over_published'], ratio)} of published volume. Single days are noisy (correlation with the published series {r2(RC.get('corr_deposit_vs_published'))}): one large deposit in a sampled window moves a day's point a lot.",
 "Deposits are <code>nep245:mt_mint</code> events and withdrawals are <code>mt_burn</code> events emitted by intents.near, valued at each day's USD price. Each UTC day uses only that day's windows, scaled by blocks per day ÷ blocks sampled. Published volume is DefiLlama's NEAR Intents series, which reads NEAR's own Dune table. Daily points rest on ~24 short windows, so they are noisy; the 30-day ratio is the test.")}
{panel("Transactions touching intents.near per day", chart_tx,
 f"The sample estimates <b>{num(TPD['transactions'][0])}</b> transactions a day. Where exact counts are available the sample is {ratio(RC.get('sample_tx_over_exact_tx'))} the true figure, which is the check that the sampling works.",
 "Exact counts come from the <code>txs_count</code> field of the FastNEAR transactions API for each UTC day (<code>scripts/fetch_public.py</code>). The sample estimate is transactions in sampled windows times the expansion factor.")}
</div>
{LONG_HTML}

<h2>2. Who holds the ledger? Mostly the confidential treasury</h2><p>{e(T_TXT['T4'])}</p>
<div class="grid g2" style="margin-bottom:14px">
{panel("Value shielded into Confidential Intents per day", chart_shield,
 e(CONF_TXT),
 f"Shielded value is the USD value of <code>dip4:transfer</code> events whose receiver is <code>{short(CF['treasury'])}</code>. The account is identified from NEAR's documentation, which lists it as <code>PRIVATE_TREASURY_ACCOUNT_ID</code>, ‘Treasury account for asset wrapping’, and describes the transfer into it as the shield step ({e(CF['source'])}). Public swaps are <code>dip4:token_diff</code> events on intents.near, each swap counted once. Solvers also shield their own liquidity to fill confidential swaps: {pct(next((x['share'][0] for x in CF['shield_sources'] if x['type'] == 'named'), 0), 0)} of shielded value comes from named accounts, the rest from implicit accounts, so shielded value is an upper bound on confidential swap size, not a measure of it.")}
<div class="panel"><h3>Why this matters for the thesis</h3>
<p class="say"><b>For.</b> Privacy is something NEAR Intents sells that most cross-chain venues do not, and the flow has moved to it quickly. Shielded value alone is {ci(PSP, ratio) if PSP else 'n/a'} of the published daily volume.</p>
<p class="say"><b>Against.</b> Per NEAR's documentation the confidential swap itself executes against a separate private contract (<code>intents.far</code>), not on <code>intents.near</code>. From the public chain we can count what goes in and what comes out, but not who traded what with whom. As this share grows, the published volume becomes a figure outsiders can check less and less.</p>
{f'<p class="say"><b>And the take moved too.</b> {e(TAKE_TXT)}</p>' if TAKE_TXT else ''}
<p class="say"><b>Also.</b> The treasury account backs every shielded balance, so it is a custody concentration by design. Who holds its keys, and under what controls, is not something the chain shows. It is the first question we would ask the team.</p></div>
</div>
{f"""<div class="grid g2" style="margin-bottom:14px">
{panel("When swaps left the public contract", chart_switch, e(SW_TXT + SW_NOW + SW_UNC),
 f"For each day: sampled transactions with at least one <code>dip4:token_diff</code> event, divided by all sampled transactions that day. The break date ({SW['first_day_after']}) is {e(SW['method'])}. Intervals are window bootstraps within each period.")}
{panel("Open swaps vs shielded value, per day", chart_pubshield, e(SW_PUB),
 "Open swaps: USD value of <code>dip4:token_diff</code> events, each swap counted once. Shielded: USD value of transfers into the treasury. Both are sample estimates scaled to a full day, so single days are noisy; compare the two periods, not two days. The published figure is DefiLlama's daily volume for NEAR Intents. We have not seen how that figure is built, so we report the gap and do not claim to know what fills it.")}
</div>""" if SW else ""}
{f"""<div class="grid g2" style="margin-bottom:14px">
{panel("What the treasury holds right now", chart_tb, e(TB_TXT),
 f"One view call, <code>mt_batch_balance_of</code> on <code>intents.near</code> for the treasury account across the {TB['assets_listed']} assets in the 1Click list, valued at the list price fetched in the same run (<code>scripts/treasury.py</code>). Bars are each asset's share of the total.")}
<div class="panel"><h3>Can the reserves be checked? Only one side</h3>
<p class="say"><b>Assets: yes.</b> Anyone can read the treasury's holdings on the public contract at any block, as we did.</p>
<p class="say"><b>Liabilities: no.</b> The claims against those holdings are the shielded balances on the private contract. Their total is not published, so nobody outside can confirm that holdings cover claims.</p>
<p class="say"><b>Our sample cannot fill the gap.</b> Sampled inflow minus outflow is {usd(CF['shield_usd_per_day'][0] - CF['unshield_usd_per_day'][0], 0)} a day, but each side is uncertain by tens of millions a day, so the difference says nothing reliable about the balance. A real check needs either a full count of every transfer or NEAR publishing the shielded supply.</p></div>
</div>""" if TB else ""}
{f"""<div class="grid g2" style="margin-bottom:14px">
{panel("Who shields: many accounts, two big solvers", chart_shd, e(SHD_TXT),
 "Each transfer into the treasury is credited to its sender. Shares are of total shielded value, with 95% window-bootstrap intervals. Accounts seen in a single window have intervals that reach zero: one large transfer was sampled, and we cannot say how often that account shields. Named accounts are labelled by their on-chain name only.")}
<div class="panel"><h3>How to read the confidential numbers</h3>
<p class="say"><b>What is measured.</b> Value crossing the boundary between the public contract and the treasury, in both directions, and what the treasury holds.</p>
<p class="say"><b>What is inferred.</b> That a transfer into the treasury is the first step of a confidential swap. This rests on NEAR's documentation and on every sampled transfer into the treasury carrying a long opaque memo that no other transfer has, not on seeing the swap or reading the memo.</p>
<p class="say"><b>What is unknown.</b> How many shielded dollars are swapped, how often, between whom, and at what price. Nothing in this report estimates those.</p></div>
</div>""" if SHD else ""}
<div class="grid g2">
{panel("Share of value SENT inside the ledger, by account", chart_send,
 f"Top account {ci(LED['top1_sender_share'])}; top three {pct(LED['top3_sender_share'][0])}. Sender HHI {num(LED['sender_hhi'])} (above 2,500 is ‘highly concentrated’ in antitrust practice).",
 "Every <code>dip4:transfer</code> event is valued in USD and credited to its <code>account_id</code> (sender). Whiskers are 95% window-bootstrap intervals.")}
{panel("Share of value RECEIVED inside the ledger, by account", chart_recv,
 f"Top account {ci(LED['top1_receiver_share'])}; top three {pct(LED['top3_receiver_share'][0])}. {num(LED['distinct_receivers'])} distinct receivers appear in the sample.",
 "Same events, credited to <code>receiver_id</code>.")}
</div>
<div class="panel" style="margin-top:14px"><h3>Standing accounts: seen in at least 5% of windows</h3>{stand_tbl}
<p class="say">Only <b>{num(ST['count'])}</b> of {num(ST['accounts_seen'])} accounts in the sample are there day in, day out. <b>{ci(ST['share_touching_standing'])}</b> of the value has one of them on at least one side. {num(ST['accounts_seen_once'])} accounts ({pct(ST['accounts_seen_once'] / max(1, ST['accounts_seen']), 0)}) appear in a single window: single-use deposit accounts, which is why wallet counts say nothing about users here.</p></div>

<div class="grid g2" style="margin-top:14px">
{panel("The other settlement path: token_diff, by account", chart_diff,
 f"{pct(LED['token_diff_share_of_events'], 0)} of trade events are direct <code>token_diff</code> swaps, worth about <b>{usd(TPD['token_diff_usd'][0] / 2)}</b> a day (each swap is counted once). Here {num(LED['distinct_token_diff_accounts'])} accounts take part and the largest has {ci(LED['token_diff_accounts'][0]['share'])}: several solvers compete on this path.",
 "For every <code>dip4:token_diff</code> event the positive legs (what the account receives) are valued in USD and credited to the account. Both sides of a swap emit an event, so the daily total is halved to count each swap once.")}
<div class="panel"><h3>Who brings the flow: referral tags on token_diff</h3>{ref_tbl}
<p class="say">{num(N['referral_events'])} of {num(N['token_diff_events'])} token_diff events carry a referral tag. Shares are of tagged value only, so read them as a ranking of distribution partners, not as market share.</p></div>
</div>

<h2>3. Where does the money come from, and where does it go?</h2><p>{e(T_TXT['T2'])}</p>
<div class="grid g2">
{panel("Deposits by source chain", chart_dep, f"{cn(dep0['chain'])} leads with {pct(dep0['share'][0])}. Chain HHI {num(CH['deposit_hhi'])}.",
 "USD value of <code>mt_mint</code> events grouped by the chain of the minted asset (1Click token list).")}
{panel("Withdrawals by destination chain", chart_wd, f"{cn(wd0['chain'])} leads with {pct(wd0['share'][0])}. Chain HHI {num(CH['withdrawal_hhi'])}.",
 "USD value of <code>mt_burn</code> events grouped by the chain of the burned asset.")}
</div>
{FLOW_HTML}

<h2>4. What is being moved?</h2><p>{e(T_TXT['T3'])}</p>
<div class="grid g2">
{panel("Assets moved inside the ledger", chart_asset, f"Stablecoins: <b>{ci(AS['stable_share'])}</b>.",
 "USD value of <code>dip4:transfer</code> legs by token symbol.")}
<div class="panel"><h3>Size of a transfer</h3>{table(["Statistic", "Value"], [["Transfers in sample", num(SZ['n'])], ["Median", usd(SZ['median'])], ["90th percentile", usd(SZ['p90'])], ["99th percentile", usd(SZ['p99'])], ["Largest", usd(SZ['max'])], ["Value from transfers ≥ $100K", e(ci(SZ['share_from_100k_plus']))]])}
<p class="say">The median transfer is small and a few very large ones carry much of the value. That is why every share on this page comes with an interval: one whale in a sampled window moves the point estimate.</p></div>
</div>

<h2>5. Who submits the transactions?</h2><p>{e(T_TXT['T5'])}</p>
<div class="grid g2">
{panel("Share of transactions by signer", chart_sign, f"{num(AC['distinct_signers'])} distinct signers in the sample; the top five submit <b>{pct(AC['top5_signer_share'][0])}</b>.",
 "The <code>signer_id</code> of every sampled transaction.")}
<div class="panel"><h3>What this means</h3><p class="say">Chain abstraction works as advertised: the user signs on their own chain and a relayer puts the result on NEAR. The cost is that liveness and censorship resistance for this flow rest on a short list of relayer keys, not on NEAR's validator set alone. For an investor this is an operational-risk line, and a decentralisation roadmap item to track.</p>
{table(["Sender account type", "Share of value sent"], [[e(r['type']), e(ci(r['share']))] for r in AC['source_account_types']])}</div>
</div>
{f'<div class="grid g2" style="margin-top:14px">{TIME_HTML}<div class="panel"><h3>Why timing matters</h3><p class="say">{TIME_WHY}</p></div></div>' if TIME_HTML else ''}

<h2>6. Does NEAR capture the value?</h2><p>{e(T_TXT['T6'])}</p>
<div class="grid g2">
{panel("Monthly Intents volume and NEAR's take", chart_month,
 f"Annualised, the last 30 days of captured revenue come to <b>{usd(PUB['annualised_revenue'])}</b>. All fees paid on NEAR-chain protocols over the same 30 days: {usd(PUB['chain_fees_30d'])}.",
 "DefiLlama monthly sums of NEAR Intents volume and revenue (their adapter reads NEAR's Dune tables: gross fees, and NEAR swept into the revenue wallets). Revenue ÷ volume in basis points.")}
{panel("The track's own hypothesis: volume or price, which tracks usage?", chart_px,
 (f"Over {LEAD.get('days')} days, daily changes in intents.near transactions correlate {r2(LEAD.get('corr_tx_vs_volume_same_day'))} with changes in Intents volume and {r2(LEAD.get('corr_tx_vs_price_same_day'))} with changes in NEAR price." if LEAD else "Exact transaction counts were not fetched, so this test was not run."),
 "Pearson correlation of daily log changes; exact transaction counts from FastNEAR, volume and price from DefiLlama. ‘Previous day’ shifts volume or price back one day to see whether it leads.")}
</div>{lead_tbl}
{f'<div class="grid g2" style="margin-top:14px"><div class="panel"><h3>NEAR&#39;s take next to other cross-chain venues</h3>{PEER_HTML}<p class="say">Last 30 days. {e(PEER_TXT)}</p><details><summary>How this is computed</summary><p class="small muted">DefiLlama 30-day totals fetched {dt.datetime.fromtimestamp(PEER["fetched_at"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}: volume from <code>overview/dexs</code>, fees and revenue from <code>overview/fees</code>. “Users pay” is fees ÷ volume and “Protocol keeps” is revenue ÷ volume, both shown only where DefiLlama publishes a volume series for that venue. The list of venues was chosen by us (<code>PEERS</code> in <code>scripts/fetch_public.py</code>); adapters differ in what they count, so treat this as a rough comparison.</p></details></div>{VAL_HTML}</div>' if PEER else ''}

<h2>7. Does it hold up? Robustness</h2>
<p>One sample can be lucky. So every sample-based test was run again: on an independent second sample drawn with a different seed, on the two samples pooled, on each half of the period, with every item of $100K or more removed, and with a different price source. A coloured dot is the verdict under the same pre-set rule (green supported, amber inconclusive, red contradicted).</p>
<div class="panel rob">{rob_tbl}<p class="say">{e(ROB_SAY + THIRD_TXT)} “Whales removed” is not a fair test of T1, because large deposits are about half of the value by construction; it is shown for the share tests only.</p></div>

<h2>8. Is it still true today? The daily tracker</h2>
<p>The snapshot above is frozen so that anyone can rebuild it. To see whether it keeps holding, <code>scripts/track.py</code> draws a small fresh sample of the last 24 hours ({TRK[-1]['strata'] if TRK else 96} windows, seed = the date) and appends one row here. A scheduled GitHub Action runs it once a day and republishes this page. One day of {TRK[-1]['strata'] if TRK else 96} windows is a thin sample, so the intervals are wide and no verdict is issued from a single row: read the direction over several days.</p>
{TRK_HTML}
{PRED_HTML}

<h2>9. Move the goalposts yourself</h2>
<p>Disagree with a threshold? Drag it. The verdict is recomputed in your browser with the same rule: the pooled interval must be wholly on one side, and both samples' point estimates must agree.</p>
<div class="panel"><div id="sl"></div></div>
<script>
const SL = {json.dumps([{"id": t, "claim": V[t]["claim"], "rule": TBY[t]["rule"], "th": TBY[t].get("threshold"), "pooled": POOL[t], "main": ROB[0][t][0], "repl": REPL[t][0]} for t in ("T2", "T3", "T4", "T5")] if POOL and REPL else [])};
const col = {{supported: "{GOOD}", contradicted: "{BAD}", inconclusive: "{WARN}"}};
function side(rule, th, p) {{ return (rule === "above") === (p > th); }}
function judge(t, th) {{
  const [p, lo, hi] = t.pooled, up = t.rule === "above";
  let v = (up ? lo > th : hi < th) ? "supported" : (up ? hi < th : lo > th) ? "contradicted" : "inconclusive";
  if (side(t.rule, th, t.main) !== side(t.rule, th, t.repl)) v = "inconclusive";
  return v;
}}
const box = document.getElementById("sl");
SL.forEach(t => {{
  const row = document.createElement("div"); row.className = "slrow";
  row.innerHTML = `<div><b>${{t.id}}</b> ${{t.claim}}<br><span class="muted small">pooled ${{(t.pooled[0]*100).toFixed(1)}}% (${{(t.pooled[1]*100).toFixed(1)}}–${{(t.pooled[2]*100).toFixed(1)}}%), main ${{(t.main*100).toFixed(1)}}%, replication ${{(t.repl*100).toFixed(1)}}%</span></div>
    <div><input type="range" min="0" max="100" step="1" value="${{t.th*100}}" aria-label="threshold for ${{t.id}}"> <span class="thv"></span> <span class="badge"></span></div>`;
  const inp = row.querySelector("input"), thv = row.querySelector(".thv"), bd = row.querySelector(".badge");
  const upd = () => {{ const th = inp.value / 100, v = judge(t, th); thv.textContent = `pass if ${{t.rule}} ${{inp.value}}%`; bd.textContent = v; bd.style.background = col[v]; }};
  inp.addEventListener("input", upd); upd(); box.appendChild(row);
}});
</script>

<h2>10. What would change our mind</h2>
<ul><li>T1 fails on a re-sample (deposits wholly outside 0.5×–2× of published volume): the demand story is not verifiable and the thesis falls.</li>
<li>The top five signers fall below 90% of transactions: the access dependency is easing.</li>
<li>Public swaps return to the public contract, or the tracker's shielded share falls back below 90% (prediction P2): the audit gap was temporary.</li>
<li>NEAR publishes verifiable aggregates for the confidential ledger (volume, solver count, treasury controls): the audit gap closes and the confidential share becomes a plain positive.</li>
<li>NEAR's captured revenue stays above 5 bps of volume for three months without volume falling: the value-capture objection is answered.</li>
<li>One chain rises above half of deposits: the product has become a single-corridor bridge and should be valued as one.</li></ul>

<h2>11. Method and limits</h2>
<ul><li><b>Sampling.</b> The {num(G['windows_drawn'])} most recent strata of {num(G['sample_config']['stratum_blocks'] if G['sample_config'] else 0)} blocks before height {num(G['sample_config']['end_height'] if G['sample_config'] else 0)}; one window of {num(G['sample_config']['window_blocks'] if G['sample_config'] else 0)} consecutive blocks per stratum, position drawn with seed {G['sample_config']['seed'] if G['sample_config'] else ''}. {num(G['windows_used'])} windows were fully downloaded and used.</li>
<li><b>It is a sample.</b> Shares carry intervals; totals are estimates. Rare, very large transfers make value shares noisier than count shares.</li>
<li><b>Prices.</b> {pct(G['legs_priced_at_day_price'])} of token legs are valued at the asset's USD price on the day of the transaction (DefiLlama daily series); the rest use the 1Click list price at fetch time. Intraday moves are not captured. The robustness table shows the effect of using a single price list instead.</li>
<li><b>Accounts are not people.</b> One account is identified from NEAR's public documentation (the Confidential Intents Treasury). Every other account is described by behaviour only; we do not claim to know who operates it.</li>
<li><b>The confidential side is seen from outside only.</b> We measure value entering and leaving the treasury on the public contract. What happens on the private contract is taken from NEAR's documentation, not observed.</li>
<li><b>Two settlement paths.</b> {pct(1 - LED['token_diff_share_of_events'], 0)} of trade events in the sample are <code>transfer</code> intents and {pct(LED['token_diff_share_of_events'], 0)} are <code>token_diff</code> swaps. Tests T3 and T4 are measured on the transfer path ({usd(TPD['transfer_usd'][0])} a day of internal movement, which counts each hop); token_diff is reported separately in section 2.</li>
<li><b>Deposits are not swaps.</b> T1 compares value entering the contract with published swap volume. They are different things that should be of the same order; a ratio near 1 is not expected, a ratio of 0.1 or 10 would be a problem.</li>
<li><b>Thresholds.</b> Fixed after a 6-window pilot and before the full sample was drawn, and not changed afterwards.</li>
<li><b>The combining rule came later.</b> The rule for combining the main and replication samples (pooled interval, both point estimates on the same side) was written after both samples were drawn. Under a stricter rule, where each sample must pass on its own, T1 would also be inconclusive, because the smaller replication sample's interval starts at {ratio(REPL['T1'][1]) if REPL and REPL.get('T1') else 'n/a'}, just under the 0.5× bound.</li>
<li><b>Pooling.</b> Pooled figures are an inverse-variance average of the two samples using a normal approximation to each bootstrap interval. Where the two samples disagree (T2, T4) the pooled interval is too narrow, which is the reason for the second condition.</li>
<li><b>Not run.</b> The BigQuery cross-checks in <code>sql/</code> were written but not executed (no billing account). The Intents Explorer API needs a partner JWT and was not used.</li>
<li>Research, not investment advice.</li></ul>
<h2>12. Try to prove it wrong</h2>
<p>Each of these can break a claim on this page. All run from a fresh clone.</p>
{table(["If you doubt", "Do this", "The claim fails if"],
 [["the numbers match the raw data", "<code>python3 rebuild.py</code>", "<code>git diff</code> shows any change in <code>THESIS.md</code> or <code>data/derived/numbers.json</code>"],
  ["the sample was cherry-picked", "<code>python3 tests/test_all.py</code>", "the windows on disk are not the ones the seed produces (the test re-derives both plans)"],
  ["the result depends on this one sample", "<code>python3 rebuild.py --resample</code> (about 40 min)", "T3 or T5 changes verdict on a fresh seed"],
  ["the switch to confidential settlement", "<code>python3 rebuild.py --track</code> (about 10 min)", "the new row's shielded share is under 90%"],
  ["the treasury figure", "<code>python3 scripts/treasury.py</code>", "the total is far from the one shown in section 2"],
  ["a threshold was chosen to flatter", "drag the sliders in section 9", "a small move flips a ‘supported’ verdict"]], "small wrapc")}
<p class="small muted">Data behind the charts, as CSV: {" · ".join(f'<a href="data/{n}">{n}</a>' for n in CSVS)}</p>

<h2>13. Primer, glossary and sources</h2>
<p>New to NEAR Intents? A user on another chain deposits, the public contract keeps the ledger, and swaps are settled either in the open or, increasingly, on a private contract behind one treasury account. Relayers submit nearly every transaction.</p>
<div class="panel">{FLOW_SVG}<p class="say">Solid boxes are things this project reads directly from the chain. The dashed box is described in NEAR's documentation and cannot be observed from outside.</p></div>
<div class="grid g2" style="margin-top:14px"><div class="panel"><h3>Glossary</h3>{GLOSS_TBL}</div><div class="panel"><h3>Sources</h3>{SRC_TBL}
<p class="small muted">Longer versions in the repository: <code>PRIMER.md</code> (how it works), <code>METHODOLOGY.md</code> (estimators, event dictionary, a worked example), <code>TUTORIAL.md</code> (seven hands-on exercises), <code>SOURCES.md</code> (every endpoint and reference).</p></div></div>

<h2>14. Reproduce</h2><pre>git clone &lt;this repo&gt; &amp;&amp; cd near-intents-xray
python3 rebuild.py              # rebuild every number and chart from the committed raw samples (offline, ~3 min)
python3 rebuild.py --fetch      # also refresh DefiLlama, 1Click prices and exact tx counts
python3 rebuild.py --track      # measure the last 24 hours and add a row to the daily tracker (~10 min)
python3 rebuild.py --resample   # draw a fresh sample from mainnet (keyless, ~40 min)</pre>
<p class="small muted">Python 3.9+, standard library only. Sources: FastNEAR transactions API, DefiLlama, 1Click token list.</p>
</div></body></html>"""
import re as _re
_NAV = {"1": "Volume", "2": "Confidential", "3": "Chains", "4": "Assets", "5": "Access", "6": "Revenue", "7": "Robustness",
        "8": "Tracker", "9": "Sliders", "10": "Change our mind", "11": "Limits", "12": "Prove it wrong", "13": "Primer", "14": "Reproduce"}
_secs = _re.findall(r"<h2>(\d+)\. ", HTML)
HTML = _re.sub(r"<h2>(\d+)\. ", lambda m: f'<h2 id="s{m.group(1)}">{m.group(1)}. ', HTML)
_nav = ('<nav class="nav" id="nav"><a href="#top">Summary</a>' + "".join(f'<a href="#s{n}">{n} {_NAV.get(n, "")}</a>' for n in _secs) + "</nav>"
        "<script>(function(){const L=[...document.querySelectorAll('#nav a')],H=L.map(a=>document.getElementById(a.getAttribute('href').slice(1)));"
        "function u(){let i=0;H.forEach((h,j)=>{if(h&&h.getBoundingClientRect().top<90)i=j});L.forEach((a,j)=>a.classList.toggle('on',j===i))}"
        "addEventListener('scroll',u,{passive:true});u()})();</script>")
HTML = HTML.replace('<div class="view">', _nav + '<div class="view">', 1).replace('<div class="wrap">', '<div class="wrap" id="top">', 1)
os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
open(os.path.join(ROOT, "docs", "index.html"), "w").write(HTML)
print("wrote docs/index.html")
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "thesis_md.py")).read())
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.py")).read())
