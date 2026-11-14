# Executed by build_report.py (shares its namespace). Writes docs/report.html: the thesis as a research note,
# laid out for A4 print. Every figure comes from the same variables as the dashboard; nothing is typed in by hand.
_today = dt.datetime.fromtimestamp(PUB["fetched_at"], dt.timezone.utc).strftime("%d %B %Y")
_cnt = {k: sum(1 for t in V if V[t]["verdict"] == k) for k in ("supported", "contradicted", "inconclusive")}
_tot_tx = sum(r["transactions"] for r in ROB if r["name"] in ("Main sample", "Replication sample", "Third sample"))
_tot_w = sum(r["windows"] for r in ROB if r["name"] in ("Main sample", "Replication sample", "Third sample"))
_ann, _vday, _take = PUB["annualised_revenue"], PUB["volume_30d"] / 30, PUB["rev_bps_30d"]
_mc = MKT["market_cap"] if MKT else None
_t1 = (_p3 or POOL)["T1"] if (_p3 or POOL) else RC["deposit_over_published"]


def _val(t):
    v = V[t]
    f_ = ratio if t == "T1" else bps if t == "T6" else pct
    s_ = f_(v["value"])
    return s_ + (f" ({f_(v['lo'])}–{f_(v['hi'])})" if v.get("lo") is not None and t != "T6" else "")


def _rule(t):
    v = V[t]
    return f"between {v['low']}× and {v['high']}×" if v["rule"] == "between" else (f"above {v['threshold']} bps" if t == "T6" else f"{v['rule']} {pct(v['threshold'], 0)}")


def ex(n, title, body, src):
    return (f'<figure class="ex"><figcaption><b>Exhibit {n}.</b> {e(title)}</figcaption>{body}'
            f'<div class="src">Source: {e(src)}; X-Ray calculations.</div></figure>')


SRC_CHAIN = "seeded sample of intents.near transactions (FastNEAR), 1Click price list, DefiLlama daily prices"
# ---- scenarios
_grid_v, _grid_t = [0.5, 1, 2, 4], [_take, 10, PUB["fee_bps_30d"], 25]
_grid = table(["Volume a day ↓ / NEAR's take →"] + [bps(t_) + (" (today)" if t_ == _take else " (all user fees today)" if t_ == PUB["fee_bps_30d"] else "") for t_ in _grid_t],
              [[f"{usd(_vday * m_, 0)}" + (" (today)" if m_ == 1 else f" ({m_:g}×)")] +
               [(("<b>" if (m_ == 1 and t_ == _take) else "") + f"{usd(_vday * m_ * 365 * t_ / 1e4, 0)}" + (f" · {_mc / (_vday * m_ * 365 * t_ / 1e4):.0f}×" if _mc else "") + ("</b>" if (m_ == 1 and t_ == _take) else ""))
                for t_ in _grid_t] for m_ in _grid_v], "small")
_sc = [("Bear", "Volume halves and the take stays where it is. Prediction P5 would fail first.", 0.5, _take),
       ("Base", "The last 30 days repeat for a year.", 1, _take),
       ("Bull", "Volume doubles and NEAR keeps everything users pay today, not a third of it. Needs access and fee policy to change (T5, T6).", 2, PUB["fee_bps_30d"])]
_sc_tbl = table(["Scenario", "What has to be true", "Volume a day", "Take", "Revenue a year", "Market value ÷ revenue"],
                [[f"<b>{n_}</b>", e(w_), usd(_vday * m_, 0), bps(t_), usd(_vday * m_ * 365 * t_ / 1e4, 1), f"{_mc / (_vday * m_ * 365 * t_ / 1e4):.0f}×" if _mc else "n/a"]
                 for n_, w_, m_, t_ in _sc], "small wrapc")
# ---- risks
_risks = [
    ("Verifiability", "High",
     (f"Open swaps fell from {pct(SW['before']['swap_tx_share'][0], 0)} to {pct(SW['after']['swap_tx_share'][0], 1)} of transactions; open swap value is {pct(SW['after']['public_swap_over_published'], 0)} of the published figure since {SW['after']['from']}." if SW else "n/a"),
     "NEAR publishes auditable aggregates for the confidential ledger."),
    ("Custody concentration", "High",
     (f"One treasury account holds {usd(TB['total_usd'], 0)} and backs every shielded balance; the claims against it are not published." if TB else "n/a"),
     "Disclosure of key holders, controls and the shielded supply."),
    ("Access concentration", "High", f"Five accounts submit {_val('T5')} of transactions. Same result in every run.", "Top-five share under 90% (P1 fails)."),
    ("Value capture", "Medium",
     f"NEAR keeps {bps(_take)} of volume; users pay {bps(PUB['fee_bps_30d'])}." + (f" The take went from {bps(SW['before']['rev_bps'])} to {bps(SW['after']['rev_bps'])} around the break." if SW and SW['before'].get('rev_bps') is not None else ""),
     "Take above 5 bps over 30 days (P3 fails) without volume falling."),
    ("Quality of the headline volume", "Medium",
     f"Sampled deposits are {ci(_t1, ratio)} of published volume; all three samples sit below 1×. The rest is not explained by anything we can see.",
     "A published method for the volume figure, or a full on-chain count."),
    ("Liquidity concentration", "Medium",
     (f"Two solver accounts supply {pct(sum(r['share'][0] for r in SHD['top'] if r['type'] == 'named'), 0)} of shielded value." if SHD else "n/a"),
     "More solvers taking share."),
    ("Our own measurement", "Medium",
     f"{num(_tot_w)} windows over {G['span_days']:.0f} days. Two of six tests are inconclusive; value shares depend on a few very large transfers.",
     "A larger sample or a full count; the BigQuery cross-checks, which were written but not run."),
]
_risk_tbl = table(["Risk", "Level", "Evidence in this report", "What would reduce it"],
                  [[f"<b>{e(a_)}</b>", e(b_), e(c_), e(d_)] for a_, b_, c_, d_ in _risks], "small wrapc")
_qs = ["Who controls the keys of the Confidential Intents Treasury, and what stops a single party moving its funds?",
       "Will the total shielded supply be published, so holdings can be compared with claims?",
       "How is the published volume figure built, and does it include swaps executed on the confidential ledger?",
       "Why did swaps settled on the public contract fall to almost nothing within about a week at the start of November?",
       "Who may submit transactions to the contract today, and is there a plan to open relaying to others?",
       "Why did the share of volume kept by NEAR fall in November, and what is the intended long-run take?",
       "How many independent solvers fill confidential swaps, and how is their liquidity concentrated?",
       "Which figures about the confidential ledger can an outside auditor verify today?"]

_score = table(["", "Claim tested", "Pass rule (set in advance)", "Measured", "Verdict"],
               [[f"<b>{t}</b>", e(V[t]["claim"]), e(_rule(t)), e(_val(t)), badge(V[t]["verdict"])] for t in ("T1", "T2", "T3", "T4", "T5", "T6")], "small wrapc")
_pred = table(["", "Prediction", "Met when", "Baseline", "If we are wrong"],
              [[f"<b>{r['id']}</b>", e(r["claim"]), r["pass"], r["base"], e(r["if_wrong"])] for r in PRED_ROWS], "small wrapc") if PRED_ROWS else ""
_rob_small = table(["Run", "Windows", "T1", "T2", "T3", "T4", "T5"],
                   [[e(r["name"]), num(r["windows"])] + [rob_cell(t, r) for t in ("T1", "T2", "T3", "T4", "T5")] for r in ROB], "small")

_take3 = [
    (f"The demand is real and checkable. Deposits measured on-chain are {ci(_t1, ratio)} of the published volume across three independent samples, "
     f"and {pct(V['T3']['value'], 0)} of the value moved is stablecoins. This behaves like a cross-chain dollar rail."),
    (f"Most of it can no longer be audited. Around {SW['first_day_after']} swaps left the public contract: the share of transactions carrying an open swap fell from "
     f"{pct(SW['before']['swap_tx_share'][0], 0)} to {pct(SW['after']['swap_tx_share'][0], 1)}, while about {usd(SW['after']['shield_usd_per_day'][0], 0)} a day now moves into Confidential Intents. "
     f"Published volume did not fall." if SW else ""),
    (f"One account sits behind the confidential side. The treasury named in NEAR's documentation held {usd(TB['total_usd'], 0)} when we read it. Its holdings are public; the claims against it are not." if TB else ""),
    f"Access is closed in practice. Five accounts submit {pct(V['T5']['value'], 0)} of all transactions, in every sample and every sensitivity run.",
    (f"Value capture is thin but not unusual. NEAR keeps {bps(_take)} of volume. The comparable venues we can measure keep less, and NEAR Intents earns the most revenue in dollars of the {len(PEER['rows'])} we listed." if PEER else f"NEAR keeps {bps(_take)} of volume."),
    (f"The price assumes a lot. NEAR's market value is {_mc / _ann:.0f}× annualised Intents revenue. Revenue alone does not carry the valuation in any scenario short of a doubling of volume with a much higher take." if _mc else ""),
]
_take3 = [x for x in _take3 if x]

RCSS = f"""
@page{{size:A4;margin:16mm 15mm 16mm}}
*{{box-sizing:border-box}}body{{margin:0;background:#fff;color:{INK};font:10.6pt/1.5 Georgia,"Times New Roman",serif}}
.pg{{max-width:800px;margin:0 auto;padding:26px 22px 60px}}
.sans,table,.src,.kf,.tag,figcaption,.meta,.badge,.foot{{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.mast{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid {INK};padding-bottom:8px}}
.brand{{font:700 13pt ui-sans-serif,system-ui,sans-serif;letter-spacing:.04em}}.meta{{font-size:8.5pt;color:{MUTE};text-align:right}}
.tag{{font-size:8pt;letter-spacing:.14em;text-transform:uppercase;color:{C2};font-weight:700;margin-top:18px}}
h1{{font:700 24pt/1.12 Georgia,serif;margin:4px 0 6px}}.sub{{font-size:13pt;color:#374151;margin:0 0 14px}}
h2{{font:700 14pt/1.2 Georgia,serif;margin:26px 0 6px;padding-top:10px;border-top:1.5px solid {INK};break-after:avoid}}
h3{{font:700 10.5pt ui-sans-serif,system-ui,sans-serif;margin:14px 0 4px;break-after:avoid}}p{{margin:0 0 8px}}
.two{{display:grid;grid-template-columns:1.55fr 1fr;gap:20px;align-items:start}}
.kf{{border:1px solid {LINE};border-radius:8px;padding:10px 12px;font-size:8.8pt;background:#fafaf9}}
.kf h4{{margin:0 0 6px;font-size:8pt;letter-spacing:.1em;text-transform:uppercase;color:{MUTE}}}
.kf div{{display:flex;justify-content:space-between;gap:10px;padding:3px 0;border-bottom:1px solid {LINE}}}.kf div:last-child{{border:0}}.kf b{{white-space:nowrap}}
.view{{border-left:4px solid {C1};background:#f0fdf4;padding:10px 14px;margin:10px 0 14px;font-size:11pt}}
ol.key{{padding-left:20px;margin:6px 0}}ol.key li{{margin-bottom:6px}}
table{{border-collapse:collapse;width:100%;font-size:8.6pt;margin:4px 0}}th,td{{text-align:left;padding:4px 6px;border-bottom:1px solid {LINE};vertical-align:top}}
th{{font-size:7.6pt;text-transform:uppercase;letter-spacing:.05em;color:{MUTE};border-bottom:1.5px solid {INK}}}.tw{{overflow-x:auto}}
.badge{{color:#fff;font-size:7.4pt;font-weight:700;padding:1px 7px;border-radius:99px;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}}
.ex{{margin:12px 0;break-inside:avoid}}figcaption{{font-size:9pt;margin-bottom:4px}}.src{{font-size:7.6pt;color:{MUTE};margin-top:3px}}
.chart{{width:100%;height:auto;display:block}}.g2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px}}.muted{{color:{MUTE}}}.small{{font-size:8.6pt}}
code{{font:8.4pt ui-monospace,Menlo,Consolas,monospace;background:#f3f4f6;padding:0 4px;border-radius:3px}}
.foot{{font-size:7.8pt;color:{MUTE};border-top:1px solid {LINE};margin-top:26px;padding-top:8px}}
ul{{padding-left:18px;margin:4px 0 8px}}li{{margin-bottom:3px}}
@media print{{.pg{{padding:0;max-width:none}}h2{{break-after:avoid}}}}
@media(max-width:700px){{.two,.g2{{grid-template-columns:1fr}}}}
"""
REPORT = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEAR Intents: real demand, shrinking visibility. Research note</title><style>{RCSS}</style></head><body><div class="pg">
<div class="mast"><div class="brand">NEAR INTENTS X-RAY</div><div class="meta">Research note · {_today}<br>Digital assets · Cross-chain settlement · NEAR Protocol (NEAR)</div></div>
<div class="tag">Evidence-first investment thesis</div>
<h1>NEAR Intents: real demand, shrinking visibility</h1>
<p class="sub">An on-chain audit of the contract behind NEAR's headline volume: {num(_tot_tx)} transactions, three independent samples, six tests set in advance.</p>
<div class="two"><div>
<div class="view sans"><b>Our view.</b> Constructive on demand, cautious on structure. The flow is real and mostly dollars. But most swap value now settles where outsiders cannot audit it, five accounts submit nearly every transaction, and NEAR keeps a thin slice. We give no rating and no price target: the evidence supports watching specific measures, not a number.</div>
<h3>Key takeaways</h3><ol class="key">{''.join(f'<li>{e(x)}</li>' for x in _take3)}</ol>
</div><div>
<div class="kf"><h4>Key figures</h4>
<div><span>NEAR price</span><b>${(MKT['price'] if MKT else PUB['near_price_last']):.2f}</b></div>
{f"<div><span>Market value</span><b>{usd(_mc, 2)}</b></div>" if _mc else ""}
<div><span>Published Intents volume, 30 days</span><b>{usd(PUB['volume_30d'], 2)}</b></div>
<div><span>Fees paid by users, 30 days</span><b>{usd(PUB['fees_30d'], 2)} ({bps(PUB['fee_bps_30d'])})</b></div>
<div><span>Revenue kept by NEAR, 30 days</span><b>{usd(PUB['revenue_30d'], 2)} ({bps(_take)})</b></div>
<div><span>Revenue, annualised</span><b>{usd(_ann, 1)}</b></div>
{f"<div><span>Market value ÷ that revenue</span><b>{_mc / _ann:.0f}×</b></div>" if _mc else ""}
{f"<div><span>Shielded per day since {SW['after']['from'][5:]}</span><b>{usd(SW['after']['shield_usd_per_day'][0], 0)}</b></div>" if SW else ""}
{f"<div><span>Confidential treasury holdings</span><b>{usd(TB['total_usd'], 0)}</b></div>" if TB else ""}
<div><span>Top-5 signers' share of transactions</span><b>{pct(V['T5']['value'], 1)}</b></div>
</div>
<div class="kf" style="margin-top:10px"><h4>Scorecard</h4>
<div><span>Supported</span><b>{_cnt['supported']} of 6</b></div><div><span>Contradicted</span><b>{_cnt['contradicted']} of 6</b></div><div><span>Inconclusive</span><b>{_cnt['inconclusive']} of 6</b></div>
<div><span>Sample period</span><b>{G['first_day']} → {G['last_day']}</b></div><div><span>Windows · transactions</span><b>{num(_tot_w)} · {num(_tot_tx)}</b></div></div>
</div></div>

<h2>1. The thesis and how it was tested</h2>
<p>NEAR's investment case leans on one number: the volume of NEAR Intents, published from NEAR's own data tables. We asked whether an outsider can confirm that number and what stands behind it. Six claims were written down with pass rules before the data was analysed. Each was then tested on a seeded random sample of the contract's transactions, repeated on a second sample, and checked out-of-sample on a third drawn after the rules were fixed.</p>
{ex(1, "Six claims, their pass rules and what we measured", _score, SRC_CHAIN + "; DefiLlama for T6")}
<p class="small muted sans">T1–T5 show the pooled estimate of the first two samples with 95% intervals. A claim is supported or contradicted only when the whole interval is on one side of the rule and both samples' own estimates agree; otherwise it is inconclusive. T6 uses published figures.</p>

<h2>2. Demand: real, dollar-denominated, and somewhat smaller than published</h2>
<p>{e(T_TXT['T1'])}</p><p>{e(T_TXT['T3'])}</p>
{ex(2, "Published daily volume against deposits measured on-chain", chart_recon, SRC_CHAIN + "; DefiLlama daily volume")}
{ex("2b", "Six months of usage: exact daily transactions and published volume", chart_long, "FastNEAR exact counts; DefiLlama daily volume") + "<p>" + e(LONG_TXT) + "</p>" if LONG_HTML else ""}
<p>What cuts against it: every one of the three samples puts deposits below the published figure, and the third sample alone is inconclusive. We can confirm roughly two thirds of the headline, not all of it. Whether one chain dominates deposits is not settled: the samples disagree.</p>

<h2>3. The main finding: swaps moved out of public view</h2>
<p>{e(SW_TXT + SW_NOW + SW_UNC) if SW else ''}</p><p>{e(SW_PUB) if SW else ''}</p>
<div class="g2">{ex(3, "Share of transactions carrying a swap settled in the open", chart_switch, SRC_CHAIN)}{ex(4, "Open swaps against value shielded, per day", chart_pubshield, SRC_CHAIN)}</div>
<p>{e(ROUTER)}</p>
<p><b>For the thesis.</b> Privacy is a product most cross-chain venues do not sell, and the flow adopted it within days. {e(SHD_TXT) if SHD else ''}</p>
<p><b>Against it.</b> The swap itself executes on a separate private contract. From outside we can count what crosses the boundary, not who traded what or at what price. {e(TAKE_TXT)}</p>
<div class="g2">{ex(5, "What the confidential treasury holds, share of total", chart_tb, "mt_batch_balance_of view call on intents.near; 1Click price list") if TB else ''}<div>
<h3>Reserves can be checked on one side only</h3><p>{e(TB_TXT) if TB else ''}</p><p>The holdings are readable by anyone at any block. The shielded balances they back are not published, so nobody outside can confirm that one covers the other. Our sample cannot fill that gap: inflow and outflow are each uncertain by tens of millions of dollars a day.</p></div></div>

<h2>4. Structure: who may submit, and what NEAR keeps</h2>
<p>{e(T_TXT['T5'])}</p>
<div class="g2">{ex(6, "Share of transactions by signer", chart_sign, SRC_CHAIN)}{ex(7, "Monthly volume and NEAR's take", chart_month, "DefiLlama")}</div>
<p>{e(T_TXT['T6'])}</p>
{ex(8, "NEAR Intents next to other cross-chain venues, last 30 days", PEER_HTML, "DefiLlama 30-day totals") if PEER else ''}
<p>{e(PEER_TXT)}</p>

<h2>5. Valuation: what the price asks of Intents</h2>
<p>{f"NEAR's market value is {usd(_mc, 2)}, or {_mc / _ann:.0f}× annualised Intents revenue of {usd(_ann, 1)}." if _mc else ""} This is arithmetic on Intents revenue alone. The token is also valued for gas, staking and everything else built on NEAR, so these multiples overstate what Intents must deliver by itself. They are still the cleanest way to see how far revenue is from carrying the price.</p>
{ex(9, "Three scenarios for a year of Intents revenue", _sc_tbl, "DefiLlama; CoinGecko market value")}
{ex(10, "Sensitivity: revenue a year and market value ÷ revenue, by volume and take", _grid, "DefiLlama; CoinGecko market value")}
<p>The scenarios are illustrations with no probabilities attached. The point they make is structural: at today's take, even four times the volume leaves the multiple at {_mc / (_vday * 4 * 365 * _take / 1e4):.0f}×. The valuation case needs the take to rise, and the take is a policy choice that depends on who controls access.</p>

<h2>6. Risks</h2>
{ex(11, "Risk register", _risk_tbl, "this report")}

<h2>7. What we will watch, and when we would change our mind</h2>
<p>Five predictions were registered on {PRED['registered'] if PRED else ''} and will be graded on {PRED['horizon'] if PRED else ''}. A daily job re-samples the last 24 hours and scores them without anyone editing the result.</p>
{ex(12, "Dated predictions, scored automatically", _pred, "predictions.json; daily tracker") if _pred else ''}
<ul><li>Deposits fall wholly outside 0.5×–2× of published volume on a re-sample: the demand case is not verifiable and the thesis falls.</li>
<li>NEAR publishes auditable aggregates for the confidential ledger: the visibility objection closes and the confidential share becomes a plain positive.</li>
<li>The top five signers drop under 90% of transactions, or the take holds above 5 bps for three months without volume falling: the structural objections weaken.</li></ul>

<h2>8. Questions for the NEAR team</h2>
<ol>{''.join(f'<li>{e(q_)}</li>' for q_ in _qs)}</ol>

<h2>Appendix A. Method</h2>
<ul><li><b>Sampling.</b> The 30 days before block {num(G.get('end_height', 0)) if G.get('end_height') else 'the end height'} are cut into equal strata; one 40-block window is drawn in each with a seeded generator, and every transaction touching <code>intents.near</code> in it is downloaded with its event logs. Main sample 720 windows; two further samples of 360 windows each with different seeds.</li>
<li><b>Valuation.</b> {pct(G['price_coverage'])} of token legs are priced, most at the asset's price on the day of the transaction.</li>
<li><b>Intervals.</b> 95% window bootstrap, {num(G['bootstrap_draws'])} draws. Pooled figures are inverse-variance averages.</li>
<li><b>Check on the sampler.</b> The sample's transaction count is {RC.get('sample_tx_over_exact_tx', 0):.3f}× the exact count over the same days.</li>
<li><b>Reproduction.</b> <code>python3 rebuild.py</code> recomputes every figure in this note from the committed raw data; the test suite re-derives the sampling plan from the seeds.</li></ul>
{ex(13, "Every test under every re-check (dot: green supported, amber inconclusive, red contradicted)", _rob_small, SRC_CHAIN)}
<p class="small sans">{e(ROB_SAY + THIRD_TXT)}</p>

<h2>Appendix B. Limits</h2>
<ul><li>It is a sample over 30 days. Totals are estimates; value shares depend on a few very large transfers.</li>
<li>The confidential ledger is seen from outside only. What happens on the private contract is taken from NEAR's documentation, not observed. Shielded value includes solver liquidity and is an upper bound on confidential swap size.</li>
<li>One account is identified from NEAR's public documentation. Every other account is described by behaviour; we do not claim to know who operates it.</li>
<li>The rule for combining samples was written after the first two were drawn. The third sample was drawn after it.</li>
<li>Peer figures come from different DefiLlama adapters and are a rough comparison. The BigQuery cross-checks were written but not run.</li></ul>

<h2>Appendix C. How NEAR Intents works, and a glossary</h2>
<p>A user on another chain deposits; the public contract <code>intents.near</code> keeps the ledger; swaps settle either in the open or on a private contract behind one treasury account; relayers submit nearly every transaction.</p>
{ex(14, "The path of a swap. Solid boxes are read from the chain; the dashed box is known only from documentation", FLOW_SVG, "NEAR Intents documentation; on-chain events")}
{GLOSS_TBL}

<h2>Appendix D. Sources</h2>
{SRC_TBL}
<p class="small sans">The repository adds <code>METHODOLOGY.md</code> (estimators, event dictionary, a worked example), <code>TUTORIAL.md</code> (seven hands-on exercises) and <code>SOURCES.md</code> (every endpoint and reference, and what could not be used).</p>

<div class="foot">This note is research, not investment advice, and makes no recommendation to buy or sell any asset. It was built for NEAR HACKATHON 2026 (Investment Thesis track) with AI assistance; code, raw data and tests are in the repository, and every figure can be rebuilt with one command. Figures as of {fetched} unless dated otherwise.</div>
</div></body></html>"""
open(os.path.join(ROOT, "docs", "report.html"), "w").write(REPORT)
print("wrote docs/report.html")
