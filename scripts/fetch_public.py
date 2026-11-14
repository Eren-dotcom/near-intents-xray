#!/usr/bin/env python3
"""Pull every keyless public series the thesis uses. Writes JSON files to data/public/.

Sources
  DefiLlama  api.llama.fi         NEAR Intents daily volume, fees, revenue (their adapter reads
                                  NEAR's own Dune tables), NEAR chain fees
  DefiLlama  coins.llama.fi       NEAR daily price
  1Click     1click.chaindefuser.com/v0/tokens   asset id -> chain, symbol, decimals, USD price
  DefiLlama  coins.llama.fi       daily USD price of every listed asset (valuation at the day of transfer)
  FastNEAR   tx.main.fastnear.com EXACT count of transactions touching intents.near per window
                                  (the API returns txs_count for any block-height range)
Usage: python3 scripts/fetch_public.py [--days 45] [--only llama|tokens|counts]
"""
import argparse, datetime as dt, json, os, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "data", "public")
KEY = os.environ.get("FASTNEAR_API_KEY")
GAP = 1.15
UA = {"User-Agent": "near-intents-xray", "Content-Type": "application/json"}


def http(url, body=None, tries=6):
    fast = "fastnear" in url
    if fast and KEY:
        url += "?apiKey=" + KEY
    i = 0
    while i < tries:
        if fast:
            time.sleep(GAP)   # public endpoint allows ~60 requests a minute
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            err = e
            if getattr(e, "code", 0) == 429:
                time.sleep(20)
                continue
            i += 1
            time.sleep(1.5 * i)
    raise RuntimeError(f"{url}: {err}")


def save(name, obj):
    with open(os.path.join(PUB, name), "w") as f:
        json.dump(obj, f, separators=(",", ":"))
    print("wrote", name, flush=True)


def llama():
    out = {"fetched_at": int(time.time())}
    out["volume"] = http("https://api.llama.fi/summary/dexs/near-intents")["totalDataChart"]
    out["fees"] = http("https://api.llama.fi/summary/fees/near-intents")["totalDataChart"]
    out["revenue"] = http("https://api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue")["totalDataChart"]
    out["near_chain_fees"] = http(
        "https://api.llama.fi/overview/fees/near?excludeTotalDataChartBreakdown=true")["totalDataChart"]
    start = out["volume"][0][0]
    px = []
    while start < time.time():
        d = http(f"https://coins.llama.fi/chart/coingecko:near?start={start}&span=300&period=1d")
        pts = d["coins"]["coingecko:near"]["prices"]
        px += [[p["timestamp"], p["price"]] for p in pts]
        start += 300 * 86400
    out["near_price"] = px
    save("defillama.json", out)


PEERS = ["near-intents", "unit", "maya-protocol", "teleswap", "relay", "debridge", "across", "symbiosis", "circle-cctp"]   # DefiLlama's "thorchain" fees entry is the chain, not the swap venue, so it is left out


def peers():
    """30-day volume, fees and revenue of other cross-chain venues on DefiLlama, where DefiLlama has them.
    Many venues have fees but no volume series; those are kept with volume = null and never given a take rate."""
    q = "?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"
    vol = {p_.get("slug"): p_ for p_ in http("https://api.llama.fi/overview/dexs" + q)["protocols"]}
    fee = {p_.get("slug"): p_ for p_ in http("https://api.llama.fi/overview/fees" + q)["protocols"]}
    rev = {p_.get("slug"): p_ for p_ in http("https://api.llama.fi/overview/fees" + q + "&dataType=dailyRevenue")["protocols"]}
    rows = []
    for s_ in PEERS:
        if s_ not in fee and s_ not in vol:
            continue
        rows.append({"slug": s_, "name": (fee.get(s_) or vol.get(s_))["name"], "category": (fee.get(s_) or vol.get(s_)).get("category"),
                     "volume_30d": (vol.get(s_) or {}).get("total30d"), "fees_30d": (fee.get(s_) or {}).get("total30d"),
                     "revenue_30d": (rev.get(s_) or {}).get("total30d")})
    save("peers.json", {"fetched_at": int(time.time()), "source": "api.llama.fi overview/dexs and overview/fees, total30d", "rows": rows})


def market():
    d = http("https://api.coingecko.com/api/v3/coins/near?localization=false&tickers=false&community_data=false&developer_data=false")["market_data"]
    save("market.json", {"fetched_at": int(time.time()), "source": "api.coingecko.com/api/v3/coins/near",
                         "price": d["current_price"]["usd"], "market_cap": d["market_cap"]["usd"],
                         "fdv": d["fully_diluted_valuation"]["usd"], "circulating_supply": d["circulating_supply"]})


def tokens():
    save("tokens_1click.json", {"fetched_at": int(time.time()),
                                "tokens": http("https://1click.chaindefuser.com/v0/tokens")})


def daily_prices(days=45):
    """Daily USD prices for every listed asset with a CoinGecko id, so each transfer can be valued
    at the price of its own day instead of today's price."""
    toks = json.load(open(os.path.join(PUB, "tokens_1click.json")))["tokens"]
    ids = sorted({t["coingeckoId"] for t in toks if t.get("coingeckoId")})
    start = int(time.time()) - days * 86400
    out = {}
    for i in range(0, len(ids), 8):
        chunk = ids[i:i + 8]
        try:
            d = http("https://coins.llama.fi/chart/" + ",".join("coingecko:" + c for c in chunk) +
                     f"?start={start}&span={days + 1}&period=1d", tries=3)
        except Exception as e:
            print("  price chunk failed:", chunk, str(e)[:80], flush=True)
            continue
        for key, v in d.get("coins", {}).items():
            out[key.split(":", 1)[1]] = {
                dt.datetime.fromtimestamp(p["timestamp"], dt.timezone.utc).strftime("%Y-%m-%d"): p["price"]
                for p in v.get("prices", [])}
    save("prices_daily.json", {"fetched_at": int(time.time()), "source": "coins.llama.fi (CoinGecko ids)",
                               "prices": out})


def height_at(ts, hint_h, hint_t, cache):
    """Find the block height whose intents.near activity is closest to unix time ts.
    Uses the transactions API itself: ask for 1 tx at/below a guessed height, read its timestamp,
    correct the guess with the measured block time. Converges in 2-4 calls."""
    h = int(hint_h + (ts - hint_t) / 0.6)
    for _ in range(8):
        d = http("https://tx.main.fastnear.com/v0/account",
                 {"account_id": "intents.near", "to_tx_block_height": h, "limit": 1})
        row = d["account_txs"][0]
        t = int(row["tx_block_timestamp"]) // 10**9
        hh = row["tx_block_height"]
        cache.append((hh, t))
        if abs(t - ts) <= 30:
            return hh
        h = int(hh + (ts - t) / 0.6)
    return h


def exact_counts(days):
    """Exact daily number of transactions touching intents.near (UTC days)."""
    d = http("https://tx.main.fastnear.com/v0/account", {"account_id": "intents.near", "limit": 1})
    tip_h = d["account_txs"][0]["tx_block_height"]
    tip_t = int(d["account_txs"][0]["tx_block_timestamp"]) // 10**9
    today = tip_t - tip_t % 86400
    bounds, cache = [], []
    hint = (tip_h, tip_t)
    for i in range(days + 1):
        ts = today - i * 86400
        h = height_at(ts, hint[0], hint[1], cache)
        hint = (h, ts)
        bounds.append((ts, h))
    rows = []
    for (t_hi, h_hi), (t_lo, h_lo) in zip(bounds, bounds[1:]):
        d = http("https://tx.main.fastnear.com/v0/account",
                 {"account_id": "intents.near", "from_tx_block_height": h_lo,
                  "to_tx_block_height": h_hi - 1, "limit": 1})
        rows.append([t_lo, d["txs_count"], h_lo, h_hi - 1])
        if len(rows) % 20 == 0:
            print("  exact counts", len(rows), "/", days, flush=True)
    rows.reverse()
    save("intents_tx_counts.json", {"fetched_at": int(time.time()), "note":
         "rows: [utc_day_start, exact tx count touching intents.near, first_height, last_height]",
                                    "rows": rows})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--only", choices=["llama", "tokens", "prices", "counts", "peers", "market"], action="append")
    a = ap.parse_args()
    only = a.only or ["llama", "tokens", "prices", "counts", "peers", "market"]
    os.makedirs(PUB, exist_ok=True)
    if "llama" in only:
        llama()
    if "tokens" in only:
        tokens()
    if "prices" in only:
        daily_prices()
    if "peers" in only:
        peers()
    if "market" in only:
        market()
    if "counts" in only:
        exact_counts(a.days)


if __name__ == "__main__":
    main()
