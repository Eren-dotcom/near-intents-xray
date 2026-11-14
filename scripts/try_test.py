#!/usr/bin/env python3
"""Try your own claim against the measured numbers, with the same rule the six tests use.

  python3 scripts/try_test.py <metric path in data/derived/numbers.json> <above|below> <threshold>
  python3 scripts/try_test.py confidential.shield_share_of_transfers below 0.5
  python3 scripts/try_test.py reconciliation.deposit_over_published between 0.5 2.0

Supported / contradicted only when the whole 95% interval is on one side; otherwise inconclusive.
This uses the main sample only (the six headline tests also require a second sample to agree)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charts import dig, judge

if len(sys.argv) < 4:
    sys.exit(__doc__)
metric, rule = sys.argv[1], sys.argv[2]
t = {"metric": metric, "rule": rule}
if rule == "between":
    t["low"], t["high"] = float(sys.argv[3]), float(sys.argv[4])
else:
    t["threshold"] = float(sys.argv[3])
v = dig(metric)
verdict, p, lo, hi = judge(t, v)
rng = f" (95% interval {lo:.4g} to {hi:.4g})" if lo is not None else ""
print(f"{metric} = {p:.4g}{rng}")
print(f"rule: {rule} {' '.join(sys.argv[3:])}  ->  {verdict.upper()}")
