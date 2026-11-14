# Sources

Every external source the project uses, what it is used for, and how to check it. All were accessed on
14 November 2026.

## Data

| Source | Endpoint | Used for | Key needed |
|---|---|---|---|
| FastNEAR transactions API | `https://tx.main.fastnear.com/v0/account`, `/v0/transactions` | Listing and downloading every sampled transaction; exact daily transaction counts | No (about 60 requests a minute) |
| NEAR RPC | `https://rpc.mainnet.fastnear.com`, `https://rpc.mainnet.near.org` (`mt_batch_balance_of` on `intents.near`) | The treasury's holdings at one block | No |
| 1Click token list | `https://1click.chaindefuser.com/v0/tokens` | Asset ids, chains, decimals, list prices | No |
| DefiLlama protocol summaries | `https://api.llama.fi/summary/dexs/near-intents`, `/summary/fees/near-intents` | Published daily volume, fees and revenue (T1, T6) | No |
| DefiLlama overviews | `https://api.llama.fi/overview/dexs`, `/overview/fees` | 30-day totals for peer venues | No |
| DefiLlama prices | `https://coins.llama.fi/chart/…`, `/prices/current/…` | Daily USD prices of every listed asset; NEAR price | No |
| CoinGecko | `https://api.coingecko.com/api/v3/coins/near` | NEAR market value | No |
| Google BigQuery | `bigquery-public-data.crypto_near_mainnet_us` | Cross-check queries in `sql/` (written, not run) | Google Cloud project |

DefiLlama's NEAR Intents volume is read by its adapter from NEAR's Dune dataset
`dune.near.dataset_near_intents_metrics`; we did not query Dune directly.

## Documentation and references

| Reference | What we took from it |
|---|---|
| NEAR Intents docs, market-maker confidential example: `https://docs.near-intents.org/integration/market-makers/confidential-example` | The treasury account id (`PRIVATE_TREASURY_ACCOUNT_ID`, "Treasury account for asset wrapping"), the private contract `intents.far`, and the description of shield, swap and recover |
| NEAR Intents docs, confidential intents overview: `https://docs.near-intents.org/integration/market-makers/confidential-intents` | Background on the confidential design |
| GitHub `near/intents`, issues #383 and #384 (October 2026) | Confirmation that the account is the Confidential Intents Treasury and that outflows should not be matched to deposits |
| NEAR Hackathon thesis prompt: `https://github.com/nearai/near-hackathon-prompt-examples/blob/main/tracks/02-thesis.md` | The brief this project answers |
| NEAR Hackathon rules: `https://nearhackathon.com/HACKATHON.md` | Submission and reproducibility requirements |

## What we could not use

| Source | Why not |
|---|---|
| NEAR Intents Explorer API | Requires a partner token |
| FastNEAR block-data service (neardata) | Rate-limited for the whole build |
| Public archival RPCs | Historic blocks not served without a key |
| BigQuery | No billing project available from the build environment |

## Other theses on the same subject

We read five other hackathon entries on NEAR's investment case before choosing this angle. They use
DefiLlama aggregates, BigQuery transaction counts, issuance models or price correlations. None reports
account-level data from the Intents contract, which is the gap this project fills.
