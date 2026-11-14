#!/usr/bin/env python3
"""Exact number of transactions touching intents.near for each of the last N UTC days (default 180).
Kept apart from the 45-day file the snapshot uses, so the frozen figures do not move.
About 15 minutes on the keyless FastNEAR endpoint. Writes data/public/intents_tx_counts_long.json."""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_public as fp

days = int(sys.argv[1]) if len(sys.argv) > 1 else 180
tmp = tempfile.mkdtemp()
real = fp.PUB
fp.PUB = tmp
fp.exact_counts(days)
d = json.load(open(os.path.join(tmp, "intents_tx_counts.json")))
d["days"] = days
json.dump(d, open(os.path.join(real, "intents_tx_counts_long.json"), "w"), separators=(",", ":"))
shutil.rmtree(tmp)
print("wrote intents_tx_counts_long.json", len(d["rows"]), "days")
