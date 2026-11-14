-- OPTIONAL cross-check on Google BigQuery (NEAR public dataset). NOT executed for this submission:
-- the author had no BigQuery billing account, so every number in the thesis comes from the keyless
-- sources in scripts/. These queries are provided so a judge with BigQuery can verify the sample
-- against the full population. Always keep the block_date filter: it bounds the scan cost.
--
-- Column names follow the NEAR BigQuery docs; because the queries were not run, treat them as
-- untested and adjust if the schema has changed.
--
-- Dataset: bigquery-public-data.crypto_near_mainnet_us

-- Q1. Exact daily transactions and distinct signers that reach intents.near.
--     Compare with data/public/intents_tx_counts.json (exact counts from FastNEAR) and with
--     "totals_per_day.transactions" in data/derived/numbers.json (sample estimate).
SELECT
  block_date,
  COUNT(DISTINCT originated_from_transaction_hash) AS txs,
  COUNT(DISTINCT signer_account_id)               AS distinct_signers
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date BETWEEN DATE '2026-10-15' AND DATE '2026-11-14'
  AND receipt_receiver_account_id = 'intents.near'
GROUP BY block_date
ORDER BY block_date;

-- Q2. Who submits the transactions (access concentration, test T5).
SELECT
  signer_account_id,
  COUNT(DISTINCT originated_from_transaction_hash) AS txs
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date BETWEEN DATE '2026-10-15' AND DATE '2026-11-14'
  AND receipt_receiver_account_id = 'intents.near'
GROUP BY signer_account_id
ORDER BY txs DESC
LIMIT 25;

-- Q3. Network-wide context: daily active signers and transactions on all of NEAR.
SELECT
  block_date,
  COUNT(*)                          AS transactions,
  COUNT(DISTINCT signer_account_id) AS active_signers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE '2026-10-15' AND DATE '2026-11-14'
GROUP BY block_date
ORDER BY block_date;
