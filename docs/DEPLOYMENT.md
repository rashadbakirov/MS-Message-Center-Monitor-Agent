# Deployment Guide 🚀

This guide explains how to deploy and monitor your Microsoft Message Center Monitor automation.

---

## 📋 Overview

The app runs automatically on GitHub Actions according to a schedule. After you've completed the setup, your workflow will:

1. **Run every 6 hours** (UTC) by default
2. **Fetch** new announcements from Microsoft 365 Message Center
3. **Summarize** them with AI
4. **Post** them to your Teams channel
5. **Avoid duplicates** automatically

---

## ✅ Prerequisites

Before you deploy, make sure you've completed the setup:

- ✅ GitHub secrets added (all 8 variables)
- ✅ Teams webhook created and tested
- ✅ Azure OpenAI deployment created
- ✅ App registration set up with permissions
- ✅ Code pushed to GitHub repository

👉 **Not done yet?** Go back to [SETUP.md](SETUP.md)

---

## 🚀 Run Your First Workflow

### Option 1: Manual Trigger (Recommended for First Time)

This lets you test without waiting for the schedule.

1. Go to your GitHub repository
2. Click the **Actions** tab (top menu)
3. In the left sidebar, click **"Microsoft Message Center Monitor (Scheduled)"**
4. Click the **Run workflow** button
5. Choose **main** branch
6. Click **Run workflow** (green button)

**What to expect:**
- The workflow will start running (you'll see a spinning icon)
- Wait 30-60 seconds for it to complete
- Check your Teams channel – you should see your first card! 🎉
- If something went wrong, see the **Troubleshooting** section below

### Option 2: Wait for Automatic Schedule

If you don't want to manually trigger it:
- The workflow will run automatically every 6 hours
- First run might take up to 6 hours to happen
- We recommend testing manually first so you catch any issues

---

## 📊 Monitor Your Workflow

### View Workflow Logs

GitHub Actions logs show you everything that happened during a run.

1. Go to **Actions** tab
2. Click on a workflow run
3. Click the **"brief_monitor"** job
4. Expand any section to see details

**Typical logs show:**
```
Setting up environment... ✅
Fetching announcements... Found 3 new items
Summarizing with AI... ✅
Posting to Teams... ✅
All done!
```

### Common Log Entries to Look For

| Log Entry | Meaning |
|-----------|---------|
| `Found X new items` | X announcements will be summarized |
| `Already sent 5 items` | Those 5 are duplicates (skipped) |
| `Posting to Teams` | Card is being sent |
| `Rate limit hit` | Hit Azure OpenAI limits (retry later) |
| `Error: 401 Unauthorized` | Check your secrets (likely incorrect) |

### Where to Find Logs

```
GitHub Repository
    ↓
Actions tab
    ↓
Workflow run (recent to oldest)
    ↓
brief_monitor job
    ↓
Log output (expandable sections)
```

---

## 🔧 Customize the Schedule

By default, the workflow runs every **6 hours at UTC**. Want to change it?

### Edit the Schedule

1. Open your repository in a code editor
2. Go to file: `.github/workflows/brief-schedule.yml`
3. Find the line that says `cron: "0 */6 * * *"`
4. Replace with your cron expression
5. Commit and push the change

### Common Cron Expressions

| Schedule | Cron |
|----------|------|
| Every 6 hours | `0 */6 * * *` |
| Every 3 hours | `0 */3 * * *` |
| Every hour | `0 * * * *` |
| Daily at 9 AM UTC | `0 9 * * *` |
| Weekdays at 9 AM UTC | `0 9 * * MON-FRI` |
| Every Monday at 8 AM UTC | `0 8 * * MON` |

**⏰ Important:** Times are in **UTC (Coordinated Universal Time)**. Calculate your local time or use a [cron time converter](https://crontab.guru/).

---

## 📄 Change Lookback Period

By default, the app checks for announcements from the last **24 hours**. You can change this.

### Where to Set It

Environment variables in `.github/workflows/brief-schedule.yml`:

```yaml
env:
  DAILY_BRIEF_LOOKBACK_HOURS: 24  # Change this number
```

### Examples

| Value | What it checks |
|-------|----------------|
| `6` | Last 6 hours |
| `12` | Last 12 hours |
| `24` | Last 24 hours (default) |
| `48` | Last 2 days |
| `168` | Last 7 days |

**Recommendation:** Keep it at 24 hours for daily runs. Adjust if you're running less frequently.

---

## 🔔 Enable/Disable Empty Notifications

By default, you get a message even when there are **no new announcements**. Want to turn that off?

### Change It

In `.github/workflows/brief-schedule.yml`:

```yaml
env:
  NOTIFY_ON_EMPTY: true   # Set to "false" to disable
```

**Examples:**
- `NOTIFY_ON_EMPTY: true` → Gets a "No announcements" message in Teams
- `NOTIFY_ON_EMPTY: false` → Silent if nothing new

---

## 🆘 Troubleshooting

### Issue: Workflow Failed with Error

1. Go to **Actions** → Click the failed run
2. Click **brief_monitor** job
3. Scroll through the logs to find the error message

### Common Errors & Fixes

#### ❌ Error: `401 Unauthorized` (Microsoft Graph)

**Cause:** Your app credentials are wrong or permissions missing

**Fix:**
1. Verify your GitHub secrets match your Azure app registration
2. Verify you've granted admin consent for Microsoft Graph permissions
3. Check that your client secret hasn't expired (they expire after 24 months by default)

```bash
# Check your secret expiration in Azure Portal:
# App registrations → Your app → Certificates & secrets
# Look for the "Expires" column
```

#### ❌ Error: `401 Unauthorized` (Azure OpenAI)

**Cause:** Your API key or endpoint is wrong

**Fix:**
1. Go to Azure Portal → Your OpenAI resource
2. Check **Keys and endpoints**
3. Verify your `AZURE_OPENAI_ENDPOINT` ends with `/`
4. Copy the correct key (Key 1 or Key 2 – either works)

#### ❌ Error: `429 Too Many Requests`

**Cause:** You've exceeded Azure OpenAI rate limits

**Fix:**
- This is normal! Azure enforces request limits based on your subscription tier
- The workflow will automatically retry after a short delay
- If it keeps happening, you might need to:
  - Increase your Azure OpenAI quota
  - Use a cheaper model (like gpt-4o-mini)
  - Reduce how often the workflow runs

#### ❌ Error: `404 Not Found` (Teams Webhook)

**Cause:** Your Teams webhook URL is expired or invalid

**Fix:**
1. Go to Microsoft Teams → Workflows
2. Create a new workflow (same steps as SETUP.md)
3. Copy the new webhook URL
4. Update your GitHub secret: `TEAMS_WEBHOOK_URL`

#### ❌ No Teams Card Posted (But No Error)

**Cause:** Either no new announcements, or webhook is failing silently

**Fix:**
1. Check the workflow logs – does it say "Found 0 items" or "Found X items"?
2. If 0 items: No new announcements (this is normal!)
3. If items found: Test your webhook URL manually (see below)

### Test Your Webhook Manually

Want to verify your Teams webhook works?

```bash
# Using curl (on Mac/Linux) or PowerShell on Windows
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"AdaptiveCard","version":"1.0","body":[{"type":"TextBlock","text":"Test Message"}]}'
```

If it works, you'll see a card in Teams immediately!

---

## 📈 Monitor Costs

GitHub Actions is free, but Azure OpenAI costs money. Here's how to check:

### See Your Azure Costs

1. Azure Portal → **Cost Management + Billing**
2. Click **Cost analysis**
3. Filter by:
   - **Resource:** Your OpenAI resource
   - **Time period:** This month
4. You'll see:
   - Estimated cost for the month
   - Cost per day

### Typical Costs

| Usage | Monthly Cost |
|-------|-------------|
| 5 announcements/day (GPT-4o) | ~$5-15 |
| 5 announcements/day (gpt-4o-mini) | ~$1-3 |
| 20 announcements/day (GPT-4o) | ~$20-40 |
| 20 announcements/day (gpt-4o-mini) | ~$5-10 |

**To reduce costs:**
1. Switch to `gpt-4o-mini` (in your GitHub secret)
2. Reduce the lookback period (fewer announcements checked)
3. Run less frequently (e.g., every 12 hours instead of 6)

---

## 🚨 Important: Keeping Secrets Safe

### ⚠️ DO:
- ✅ Store secrets in GitHub Secrets and variables
- ✅ Never put secrets in code files (`.py`, `.yml`, etc.)
- ✅ Rotate keys every 1-2 years
- ✅ Treat webhook URLs like passwords

### ⚠️ DON'T:
- ❌ Commit `.env` files with real credentials
- ❌ Post secrets in GitHub issues or discussions
- ❌ Share webhook URLs in public channels
- ❌ Use the same secret across multiple projects

---

## 🔄 Update the App

Want to get the latest version of this project?

```bash
# Navigate to your repo folder
cd MS-Message-Center-Monitor

# Add upstream remote (only first time)
git remote add upstream https://github.com/rashadbakirov/MS-Message-Center-Monitor.git

# Pull latest changes
git pull upstream main

# Push to your own fork (if you have one)
git push origin main
```

---

## 📞 Need Help?

| Issue | Where to Look |
|-------|---------------|
| Setup questions | [SETUP.md](SETUP.md) |
| How the app works | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Understanding the code | [ARCHITECTURE.md#-what-happens-at-each-step](ARCHITECTURE.md) |
| Schedule explanation | [POLLING_INTERVALS_EXPLAINED.md](POLLING_INTERVALS_EXPLAINED.md) |
| More troubleshooting | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |

---

## ✅ Deployment Checklist

Before you call it done:

- [ ] All 8 GitHub secrets added correctly
- [ ] First workflow run completed successfully
- [ ] Received a Teams card (or "no announcements" message)
- [ ] Workflow is scheduled to run automatically
- [ ] You understand how to check logs if something goes wrong
- [ ] You know how to update the schedule if needed

---

**Congratulations! 🎉** Your Microsoft Message Center Monitor is now live and monitoring for you!
