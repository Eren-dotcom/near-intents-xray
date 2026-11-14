#!/usr/bin/env python3
"""Read what the Confidential Intents Treasury holds on the public contract right now.

One view call (mt_batch_balance_of on intents.near) for every asset in the 1Click list, valued at the list
price fetched in the same run. Writes data/public/treasury_balance.json. No key needed.
This is a point-in-time reading: it says what backs the shielded balances at one block, not how it got there.
"""
import base64, json, os, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "data", "public")
TREASURY = "51e8f94d77b5e90dc9852ca6113771e11e8382ce69473a75e313e41665de7cbe"
RPCS = ["https://rpc.mainnet.fastnear.com", "https://rpc.mainnet.near.org"]
STABLES = {"USDT", "USDC", "DAI", "USD1", "USDE", "FRAX", "PYUSD", "USDS", "TUSD", "USDD"}


def http(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", "User-Agent": "near-intents-xray"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def main():
    toks = http("https://1click.chaindefuser.com/v0/tokens")
    ids = [t["assetId"] for t in toks]
    args = base64.b64encode(json.dumps({"account_id": TREASURY, "token_ids": ids}).encode()).decode()
    err = None
    for rpc in RPCS:
        try:
            r = http(rpc, {"jsonrpc": "2.0", "id": 1, "method": "query", "params": {
                "request_type": "call_function", "finality": "final", "account_id": "intents.near",
                "method_name": "mt_batch_balance_of", "args_base64": args}})["result"]
            bal = json.loads(bytes(r["result"]).decode())
            break
        except Exception as e:
            err = e
    else:
        raise SystemExit(f"no RPC answered: {err}")
    rows = []
    for t, b in zip(toks, bal):
        if int(b) and t.get("price"):
            rows.append({"asset": t["assetId"], "symbol": t["symbol"].upper(), "chain": t["blockchain"],
                         "amount": int(b) / 10 ** t["decimals"], "usd": int(b) / 10 ** t["decimals"] * t["price"]})
    rows.sort(key=lambda x: -x["usd"])
    tot = sum(x["usd"] for x in rows)
    out = {"fetched_at": int(time.time()), "block_height": r["block_height"], "rpc": rpc, "account": TREASURY,
           "assets_listed": len(ids), "assets_held": len(rows), "assets_nonzero_unpriced": sum(1 for t, b in zip(toks, bal) if int(b) and not t.get("price")),
           "total_usd": tot, "stable_usd": sum(x["usd"] for x in rows if x["symbol"] in STABLES), "rows": rows}
    json.dump(out, open(os.path.join(PUB, "treasury_balance.json"), "w"), indent=1)
    print(f"treasury holds ${tot:,.0f} in {len(rows)} assets at block {r['block_height']}")
    for x in rows[:8]:
        print(f"  {x['symbol']:8s} {x['chain']:8s} ${x['usd']:>14,.0f}")


if __name__ == "__main__":
    main()
