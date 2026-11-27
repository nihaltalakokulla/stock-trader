# Paper Trading Runbook

This runs the bot end to end with simulated money: $20,000 paper account, real
market data, real SMS approvals, no brokerage connection.

Before starting, read the backtest result in
`docs/backtests/2026-11-27-full-universe-calibrated.md`. Calibration replaced
the earlier overconfident +15.43% result with +3.61% versus SPY's +7.72%, and
equal-weight ownership returned +14.57%. This paper run validates the plumbing
and collects evidence; it is not expected to prove a profitable edge yet.

## 0. Merge the feature branch

Scheduled GitHub Actions only run from the default branch.

```powershell
cd "C:\Users\Acer\Desktop\Home Coding\stock-trader"
git checkout master
git merge --ff-only feat/stock-trader-core
git push origin master
```

Then edit `worker/wrangler.toml` and set `GITHUB_REF = "master"`, commit, and
push that one-line change.

## 1. Local sanity check

```powershell
uv sync
.\.venv\Scripts\python.exe -m stock_trader.cli train
.\.venv\Scripts\python.exe -m stock_trader.cli nightly --dry-run
```

The dry run uses an in-memory repository and prints the SMS instead of sending
it. You should see a proposal block ending with `Reply YES to approve`.

## 2. Create Supabase

1. Go to supabase.com, create a free project, and save the database password
   somewhere safe.
2. Open the SQL editor and run the entire contents of
   `supabase/migrations/0001_init.sql`.
3. In Project Settings -> API, copy:
   - Project URL -> `SUPABASE_URL`
   - `service_role` key -> `SUPABASE_SERVICE_KEY` (server only, never browser)
   - `anon` key -> dashboard only

The dashboard can read the `dashboard_*` views with the anon key. It must not be
able to write; if an anon POST to `proposals` succeeds, RLS is misconfigured.

## 3. Create Twilio SMS

1. Create a Twilio account and buy an SMS-capable US number.
2. Verify your personal phone number (required on trial accounts).
3. Complete Twilio's A2P 10DLC registration if prompted; US long-code SMS may
   not deliver without it.
4. Copy the Account SID, Auth Token, and Twilio number.

Expected cost: a small monthly number fee plus a fraction of a cent per SMS.

## 4. Add GitHub Actions secrets

In the GitHub repository: Settings -> Secrets and variables -> Actions -> New
repository secret.

| Secret | Value |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_FROM_NUMBER` | Twilio number, e.g. `+15550001111` |
| `USER_PHONE` | Your verified mobile number, e.g. `+15550002222` |
| `FINNHUB_TOKEN` | Free Finnhub API token |

Then open Settings -> Actions -> General -> Workflow permissions and select
**Read and write permissions**. The weekly training workflow commits the model
artifact back to the repo.

## 5. Train the model

GitHub -> Actions -> **train-ranker** -> Run workflow -> branch `master`.

This downloads five years of daily data, trains the ranker, and commits
`models/latest.joblib`. Wait for the green check. The nightly workflow also
trains automatically if the model file is missing.

## 6. Deploy the approval Worker

Create a fine-grained GitHub token:

- Repository access: only `stock-trader`
- Permission: **Actions: Read and write**

Keep that token private. Then:

```powershell
cd worker
npx wrangler login
npx wrangler secret put TWILIO_AUTH_TOKEN
npx wrangler secret put ALLOWED_PHONE
npx wrangler secret put SUPABASE_URL
npx wrangler secret put SUPABASE_SERVICE_KEY
npx wrangler secret put GITHUB_DISPATCH_TOKEN
npx wrangler deploy
```

`ALLOWED_PHONE` is the same number as `USER_PHONE`, in E.164 format. The
non-secret repo/owner/branch values live in `wrangler.toml`.

Copy the deployed URL, for example
`https://stock-trader-approval.YOUR-SUBDOMAIN.workers.dev`.

## 7. Point Twilio at the Worker

Twilio Console -> Phone Numbers -> your number -> Messaging configuration ->
**A message comes in**:

- Webhook URL: `https://YOUR-WORKER-URL/sms-webhook`
- Method: `HTTP POST`

The URL must match exactly; Twilio signatures include the full URL.

## 8. Dashboard

Create `dashboard/config.local.js`:

```javascript
window.STOCK_TRADER_CONFIG = {
  supabaseUrl: "https://YOUR-PROJECT.supabase.co",
  supabaseAnonKey: "YOUR-ANON-KEY",
};
```

Deploy from the repo root:

```powershell
npx wrangler pages deploy dashboard --project-name stock-trader-dashboard
```

The anon key is safe to expose because RLS only allows reads of the dashboard
views. Never put the service role key in this file.

## 9. First end-to-end paper test

1. GitHub -> Actions -> **nightly-signals** -> Run workflow (`master`).
2. Wait for the job to finish and check the logs. A proposal SMS arrives only
   if a pick clears the confidence bar; silence is a valid result.
3. When the SMS arrives, reply `YES`.
4. The Worker writes the approval, dispatches **execute-approval**, and replies
   with an acknowledgement.
5. Watch the Actions run and the dashboard. You should see the approved trade,
   the fill, and the open position.
6. Reply `STOP` to test the kill switch. The Worker confirms and sets
   `trading_paused = true`.

Resume after a kill-switch test in the Supabase SQL editor:

```sql
update settings
set value = 'false'::jsonb
where key = 'trading_paused';
```

## 10. Two-week paper routine

Each trading evening:

- Check that `nightly-signals` ran. GitHub cron is best-effort; a delay is
  normal.
- If a proposal text arrives, approve or reject before the next market open.
- Check the dashboard for open positions, stops, and alerts.
- Confirm exit texts and that closed positions disappear from the dashboard.

Weekly:

- Let `train-ranker` run Sunday and verify the model commit.
- Run `paper-report` locally or in Actions and record cash, equity, trade
  count, and drawdown.
- Compare the paper result against SPY for the same dates.

Do not connect Robinhood during this phase. Two weeks of uninterrupted paper
operation is the minimum bar before writing the live broker adapter.

## Troubleshooting

- **No text / no proposal**: check the nightly log for `No candidate cleared
  the confidence bar`, a pending proposal, or a failed data fetch.
- **Twilio 403**: the Worker URL and Twilio webhook URL differ, or the From
  number is not `ALLOWED_PHONE`.
- **Approval says expired**: reply before the next market open; proposals
  intentionally die at the open.
- **Worker approved but no execution**: confirm `GITHUB_REF` matches the branch
  containing `execute.yml`, and the dispatch token has Actions write.
- **Model missing**: run the train workflow or
  `python -m stock_trader.cli train`.
- **Supabase unreachable after a quiet week**: free projects pause without
  traffic; the daily workflow normally prevents this.
- **Schedule did not fire**: scheduled workflows run from the default branch
  only and can be delayed by GitHub.

## Live-money gate (not yet)

Before the $500 Robinhood phase:

- Paper run is stable for at least two weeks.
- No duplicate orders, orphaned approvals, or stuck positions.
- Paper drawdown is acceptable against the strategy's backtest.
- The Robinhood agentic adapter passes integration tests with review-before-place
  enabled, using a separately funded agentic account.
