# Methodology

Everything the dashboard, `THESIS.md` and the research note report is computed by `scripts/analyze.py` from
the files in `data/`. This document says exactly how. New to NEAR Intents? Read [`PRIMER.md`](PRIMER.md)
first. Want to try it hands-on? See [`TUTORIAL.md`](TUTORIAL.md). Sources are listed in
[`SOURCES.md`](SOURCES.md).

## 1. The question and the design

The published NEAR Intents volume is one number from NEAR's own data tables. We wanted figures an outsider
can rebuild from the chain: where value comes from, who settles it, who submits it. Downloading every
transaction of `intents.near` for 30 days was not possible on a keyless endpoint (about 115,000 transactions
a day, 60 requests a minute). So we use a **stratified cluster sample** and report every figure with an
interval.

| Step | What is done | Why |
|---|---|---|
| Fix the period | The 4,320,000 blocks (about 30 days) before block 224,510,585 | One end height shared by all three samples, so they cover the same days |
| Stratify | Cut the period into equal strata (main sample: 720 strata of 6,000 blocks, about one hour each) | Guarantees even coverage of every hour and day |
| Draw | In each stratum draw one window of 40 consecutive blocks with a seeded generator | A window is cheap to download in full; the seed makes the draw repeatable |
| Download | Every transaction touching `intents.near` in the window, with its event logs | No selection inside a window |
| Use complete windows only | A window is used only if every listed transaction was downloaded | Avoids bias from partial windows |

Three samples were drawn this way:

| Sample | Folder | Seed | Strata × blocks | Windows | Transactions | Role |
|---|---|---|---|---|---|---|
| Main | `data/raw/` | 20261114 | 720 × 6,000 | 720 | 22,323 | All headline charts |
| Replication | `data/raw_b/` | 777 | 360 × 12,000 | 360 | 11,284 | Second opinion; pooled with the main sample for verdicts |
| Third | `data/raw_c/` | 31337 | 360 × 12,000 | 360 | 11,387 | Out-of-sample check, drawn after the verdict rule was fixed |

`tests/test_all.py` re-derives each sampling plan from its seed and fails if the windows on disk differ.

## 2. Estimators

Let `k` index windows, `S` the stratum length and `W` the window length in blocks.

- **Totals.** For a per-window quantity `y_k` (for example USD deposited), the period total is estimated as
  `(S / W) × Σ y_k`. Each window stands for `S / W` windows (150 in the main sample). Per-day figures divide
  by the number of days covered.
- **Shares.** A share is a ratio of two totals, `Σ y_k / Σ x_k` (for example stablecoin USD over all USD
  moved). The expansion factor cancels.
- **Intervals.** Windows are resampled with replacement 2,000 times (500 for sensitivity runs) and the
  statistic is recomputed each time. The interval is the 2.5th to 97.5th percentile. Resampling whole windows
  keeps the dependence between transactions inside a window.
- **Pooling.** Two or three samples are combined by an inverse-variance average. Each sample's standard error
  is taken as (upper − lower) / 3.92, and the pooled interval is the pooled mean ± 1.96 pooled standard
  errors. This assumes roughly normal estimates; where samples disagree the pooled interval is too narrow,
  which is why verdicts also require the samples' own estimates to agree.
- **Break date.** The day swaps left the public contract is the split of the daily series (share of
  transactions carrying a `dip4:token_diff` event) that minimises within-period variance, with at least five
  days on each side. Its uncertainty comes from resampling windows within each day 1,000 times and redoing
  the split.

## 3. Verdict rule

Thresholds live in `thesis_tests.json`. They were fixed after a 6-window pilot and before the full sample was
drawn, and have not been changed.

1. Compute the pooled estimate of the main and replication samples.
2. **Supported** if the whole 95% interval passes the rule; **contradicted** if the whole interval fails it.
3. Downgrade to **inconclusive** if the two samples' own point estimates fall on opposite sides of the
   threshold, or if the interval straddles it.

Disclosure: this combining rule was written after the first two samples had been drawn. The third sample was
drawn after it and did not change any verdict. T6 uses published 30-day figures and has no interval.

## 4. Valuation

- Token amounts are converted with the decimals in the 1Click token list.
- Each leg is valued at the asset's USD price **on the day of the transaction** (DefiLlama daily prices by
  CoinGecko id). Where no daily price exists, the 1Click list price at fetch time is used.
- 99.7% of token legs are priced; 99.0% at a day price. Unpriced legs are counted and listed, not guessed.
- Sensitivity run "Prices at fetch time" values everything at one price list to show how much this matters.

## 5. Which event means what

Only logs emitted by `intents.near` itself are read. Each is an `EVENT_JSON` record.

| Event | What we take from it | Used for |
|---|---|---|
| `nep245:mt_mint` | Token and amount credited to an account | Deposits, by source chain (T1, T2) |
| `nep245:mt_burn` | Token and amount removed | Withdrawals, by destination chain |
| `dip4:transfer` | Sender (`account_id`), `receiver_id`, tokens, memo | Value moved inside the ledger; senders and receivers (T3, T4); shield and unshield |
| `dip4:token_diff` | Per-account token changes of a swap | Swaps settled in the open (positive legs, halved so each swap counts once) |
| transaction `signer_id` | Who paid for and submitted the transaction | Access concentration (T5) |
| `dip4:ft_withdraw`, `mt_withdraw`, `native_withdraw` | Counted only | Event mix |

**Shield and unshield.** A `dip4:transfer` whose receiver is the Confidential Intents Treasury
(`51e8f94d…7cbe`, named in NEAR's documentation) is counted as a shield; a transfer sent by it as an
unshield. The swap that follows runs on a separate private contract and is not visible here.

## 6. A worked example

Transaction `HRAiDXqSVGeUDUFsQcyACdUN2F2aXHbBnBhD6ZFB5gV4`, block 224,505,142, in window 0 of the main sample
(`data/raw/sample_txs.jsonl`):

```json
{"tx": "HRAiDXqS…5gV4", "h": 224505142, "t": 1794654300, "signer": "intents.near", "recv": "intents.near",
 "ev": [["dip4", "transfer", [{"account_id": "26e50399…6073",
                               "receiver_id": "51e8f94d…7cbe",
                               "tokens": {"nep141:bnb-0x55d3…7955.omdep.near": "892800024799999999851"},
                               "memo": "<184 chars>"}]],
        ["dip4", "intents_executed", […]],
        ["nep245", "mt_transfer", […]]],
 "k": 0}
```

How it is counted:

1. The token is USDT bridged from BNB Chain, 18 decimals: 892800024799999999851 / 10^18 = 892.80 USDT.
2. Valued at that day's price (about $0.999): about **$892**.
3. It is a `dip4:transfer`, so $892 is added to value moved, to the sender's total and to the receiver's.
4. USDT is a stablecoin, so it is added to the stablecoin total (T3).
5. The receiver is the treasury, so it is added to shielded value, and its memo (stored only as a length,
   starting with `<`) is counted as a long memo. Every transfer into the treasury has one
   and no other transfer in the sample does, which matches the documented encrypted recipient memo.
6. The signer is `intents.near`, so the transaction counts towards that signer's share (T5).
7. The window stands for 150 windows, so this transfer contributes about $892 × 150 to the 30-day total.

## 7. Files

**Raw sample** (`data/raw*/`):

| File | Content |
|---|---|
| `sample_config.json` | Contract, API, end height, stratum and window sizes, seed |
| `windows.jsonl` | One line per window: stratum `k`, first and last block, transaction hashes listed |
| `sample_txs.jsonl.gz` | One line per transaction: `tx` hash, `h` block, `t` unix time, `signer`, `recv`, `ev` events, `k` stratum |

**Public series** (`data/public/`): `defillama.json` (volume, fees, revenue, NEAR price), `tokens_1click.json`
(asset list and prices), `prices_daily.json`, `intents_tx_counts.json` (exact daily counts, 45 days),
`intents_tx_counts_long.json` (exact daily counts, 180 days), `peers.json`, `market.json`,
`treasury_balance.json`.

**Derived** (`data/derived/numbers.json`), top-level keys:

| Key | Content |
|---|---|
| `generated_from` | Windows, transactions, dates, price coverage, bootstrap draws |
| `totals_per_day` | Transactions, transfers, deposits, withdrawals per day, with intervals |
| `reconciliation` | Sample against published volume and exact counts (T1) |
| `chains`, `assets` | Deposits and withdrawals by chain; assets and stablecoin share (T2, T3) |
| `ledger`, `standing` | Senders, receivers, the either-side share, accounts seen in many windows (T4) |
| `access` | Signers and the top-five share (T5) |
| `confidential` | Shield, unshield, shielders, share against open swaps |
| `switch` | Break date, before and after figures, bootstrap range |
| `sizes`, `referrals`, `timing` | Transfer sizes, referral tags, hour and weekday pattern |
| `daily`, `monthly`, `public`, `lead` | Daily and monthly series, published figures (T6), correlations |
| `robustness` | Every test under every sample and sensitivity run, plus pooled rows |

## 8. Known weaknesses

- **Thirty days.** Nothing here speaks to seasonality or long-run trends in the on-chain structure.
- **Heavy tails.** Transfers of $100K or more carry about half of the value. Value shares therefore have wide
  intervals, and one sampled whale can move a daily figure a lot.
- **Cluster effect.** Transactions in one window are not independent; the window bootstrap accounts for this,
  but 40 blocks is a short window.
- **Prices.** Daily prices ignore intraday moves. Ten assets fall back to a list price.
- **Identification.** One account is identified from documentation. All others are described by behaviour.
- **Outside view of the confidential side.** We see the boundary, not the private contract.
- **Not run.** The BigQuery queries in `sql/` were written but not executed.
