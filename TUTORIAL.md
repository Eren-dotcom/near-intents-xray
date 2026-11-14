# Tutorial: learn the project by doing

Seven short exercises, from "does it run" to "add your own test". Python 3.9 or newer; no packages to
install. Exercises 1–4 work offline.

## 1. Rebuild everything (3 minutes)

```bash
python3 rebuild.py
```

You should see `all checks passed`. Then `git status` should show no change to `THESIS.md` or
`data/derived/numbers.json` (only a build timestamp in `README.md`). That is the reproducibility claim.

## 2. Read one raw transaction

```bash
python3 - <<'PY'
import json
for line in open("data/raw/sample_txs.jsonl"):
    t = json.loads(line)
    if t["tx"].startswith("HRAiDXqS"):
        print(json.dumps(t, indent=1)); break
PY
```

Follow it through section 6 of [`METHODOLOGY.md`](METHODOLOGY.md): which events it has, how the amount
becomes dollars, and which totals it adds to.

## 3. Check that the sample was not cherry-picked

```bash
python3 tests/test_all.py | grep "seeded plan"
```

The test re-creates each sampling plan from the seed in `sample_config.json` and compares it with the windows
on disk. Change one `lo` value in `data/raw/windows.jsonl` and run it again: it fails.

## 4. Move a threshold

Open `thesis_tests.json`, change T5's `threshold` from `0.9` to `0.99`, and run:

```bash
python3 scripts/build_report.py
```

The T5 card on the dashboard changes from "contradicted" to "supported". Put the value back afterwards. The
sliders in section 9 of the dashboard do the same thing without editing a file.

## 5. Test your own claim

Pick any figure in `data/derived/numbers.json` and decide your pass rule **before** you look at the number.
Then:

```bash
python3 scripts/try_test.py confidential.shield_share_of_transfers below 0.5
```

It prints the estimate, its 95% interval and a verdict under the same rule the six tests use: supported or
contradicted only when the whole interval is on one side, otherwise inconclusive. Other examples:

```bash
python3 scripts/try_test.py reconciliation.deposit_over_published between 0.5 2.0
python3 scripts/try_test.py access.self_signed_share above 0.1
```

The six headline tests are fixed in `thesis_tests.json` and also require a second sample to agree; this tool
uses the main sample only, so treat its verdict as a first look.

## 6. Measure today (10 minutes, needs network)

```bash
python3 rebuild.py --track
```

This samples the last 24 hours and adds a row to `data/history/tracker.jsonl`. Section 8 of the dashboard
shows it next to the 30-day snapshot and updates the score of the five predictions.

## 7. Draw your own sample (40 minutes, needs network)

```bash
python3 scripts/sample_onchain.py --dir raw_mine --seed 12345 --strata 360 --stratum-blocks 12000 --window 40
```

Then compare it with ours:

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, "scripts")
import analyze
o = analyze.run(raw="raw_mine", write=False, boot=500)
print(analyze.key_metrics(o))
PY
```

If your T3 or T5 comes out on the other side of its threshold, you have found a real problem with this
thesis. Please open an issue.

## Optional: the BigQuery cross-check

`sql/bigquery_intents_usage.sql` holds three queries against NEAR's public BigQuery dataset. They were
written but not run. If you have a Google Cloud project, run them and compare Q1 with
`data/public/intents_tx_counts.json`: the counts should match day by day.
