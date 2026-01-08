# Schedule Explained ⏱️

The monitor runs on GitHub Actions every 6 hours (UTC).

## Default schedule
- Cron: `0 */6 * * *`
- Runs 4 times per day

## Lookback window
The workflow looks back 24 hours and de-duplicates items, so missed runs do not cause gaps.

## Change the schedule
Edit `.github/workflows/brief-schedule.yml` and update the cron expression.
