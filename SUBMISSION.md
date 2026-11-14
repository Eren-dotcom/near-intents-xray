# Submission kit (for the team lead — not part of the thesis)

Deadline: **14 Nov 2026, 23:59 UTC** (15 Nov, 05:29 IST). The form accepts one submission per repository.

## 1. Push the repository (must be public)

```sh
cd near-intents-xray
git init -b main && git add -A && git commit -m "NEAR Intents X-Ray: sampled on-chain thesis"
git remote add origin https://github.com/<you>/near-intents-xray.git
git push -u origin main
```

Then turn on the hosted demo (2 minutes, and judges prefer a link they can open): GitHub → Settings → Pages →
"Deploy from a branch" → `main`, folder `/docs`. The dashboard appears at `https://<you>.github.io/near-intents-xray/`.
Put that link in the X post.

## 2. Demo post on X (you post it; attach `docs/screenshot.png` or a 30–60 s screen recording)

Record: open `docs/index.html` → scroll the six verdict cards → run `python3 rebuild.py` in a terminal → show "all checks passed".

Draft (fits in 280 characters; replace the link):

> I sampled 44,994 mainnet txs on NEAR Intents. About 78% of the value I can see settling now goes into Confidential Intents, a ledger outsiders can't audit. Good for privacy, hard to verify. How would you check it?
> <link>
> @NEARProtocol #NEARHackathon

Longer thread (optional):

> 1/ The account at the centre of the public ledger is the Confidential Intents Treasury (named in NEAR's own docs). About $85M a day is shielded into it.
> 2/ The flow is real: sampled deposits are 0.70× the published volume (two samples pooled), and the sampled tx count is 0.97× the exact count. 72% is stablecoins.
> 3/ The catches: 5 accounts submit 98% of transactions, and NEAR keeps 4.9 bps of volume.
> 4/ What I could not settle: whether one chain dominates deposits. Two samples disagree, so the dashboard says "inconclusive".
> 5/ One command rebuilds every number from raw data. Repo: …

Check the figures against `README.md` before posting; they are regenerated on every build.

## 3. Form fields (https://nearhackathon.com/#apply)

- Project name: `NEAR Intents X-Ray`
- Tracks: `Investment Thesis`
- Team lead, email, team size, NEAR wallet address: **yours** (a mainnet account you control)
- Repository link, demo post link: from steps 1 and 2
- Leave "Website" empty unless you have one (the API treats it as a spam trap).

"What did you build?" (under 2,000 characters):

> NEAR's investment case rests on NEAR Intents volume, a figure from NEAR's own Dune tables. Outsiders cannot tell from it whether the flow is real or who settles it. NEAR Intents X-Ray measures the contract itself.
>
> It draws a seeded, stratified random sample of mainnet (720 one-hour strata over 30 days, one 40-block window each), downloads every intents.near transaction in those windows with its event logs, values each token leg at that day's price, and expands the sample to population estimates with 95% bootstrap intervals. Two more independent samples re-test every claim: 44,994 transactions in total. Six claims are tested against thresholds fixed in advance.
>
> Main finding: the account at the centre of the public ledger is the Confidential Intents Treasury named in NEAR's docs. About $85M a day is shielded into it. Swaps settled in the open fell from 22% of transactions to under 3% on each of the last 10 days, while published volume did not fall. Demand for privacy is real, but most swaps now happen where outsiders cannot audit them. The treasury's holdings ($129M) are readable; the balances they back are not.
>
> Other findings: sampled deposits are 0.70× the published volume and the sampled transaction count is 0.97× the exact count, so the demand is verifiable. Stablecoins are 72% of value moved. Five accounts submit 98% of transactions, and NEAR captures 4.9 bps of volume. Two claims are inconclusive because the two samples disagree.
>
> Deliverables: a 12-page research note (PDF), a dashboard with a live strip, threshold sliders, a daily tracker that scores five dated predictions, a generated THESIS.md (evidence for, against, what would change our mind), a robustness table, and one command (python3 rebuild.py) that recomputes everything from committed raw data. No API keys needed.
>
> NEAR's role: the subject is NEAR's verifier contract. Its structured dip4 and nep245 events make cross-chain flow auditable in one place, which is what makes this measurement possible.

## Live data (after you push)

- **Live strip:** works by itself once GitHub Pages is on. Nothing to set up.
- **Daily tracker:** runs at 03:17 UTC every day through `.github/workflows/daily.yml`. To start it straight away,
  open the repository's **Actions** tab → **daily-tracker** → **Run workflow**. If the run fails at the push step,
  go to **Settings → Actions → General → Workflow permissions** and choose **Read and write permissions**.
- **Optional:** add a repository secret named `FASTNEAR_API_KEY` to make the daily run faster. Never commit a key.
