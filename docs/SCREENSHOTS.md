# Screenshots Guide 📸

This page shows what you'll see during setup and deployment.

---

## Teams Announcement Card

**What it looks like in Microsoft Teams:**

![Teams card with AI summary](screenshots/teams-card.png)

This is what a message center announcement looks like after being summarized by AI. The card includes:
- **Title** – The announcement headline
- **AI Summary** – What changed and why it matters
- **Impact Level** – Color-coded importance (Critical, Important, etc.)
- **Action Items** – What you should do about it
- **Link** – Link to the full announcement in Microsoft 365

---

## GitHub Actions Workflow Run

**What it looks like in your GitHub repository:**

![GitHub Actions workflow run](screenshots/actions-run.png)

This shows:
- ✅ Workflow completed successfully (green checkmark)
- ⏱️ How long the run took (usually 30-60 seconds)
- 📊 When it ran and any summary info
- Click on a run to see detailed logs

**How to find this:**
1. Go to your GitHub repository
2. Click the **Actions** tab
3. Scroll to see all your workflow runs (newest first)
4. Click any run to see logs and details

---

## App Registration Permissions

**What to see in Azure Portal (App Registrations → Your App → API Permissions):**

![App registration permissions](screenshots/app-registration-permissions.png)

You should see:
- ✅ `ServiceMessage.Read.All` – Permission to read Message Center announcements
- ✅ `ServiceHealth.Read.All` – Permission to read Service Health status
- ✅ **Admin consent granted** – Green checkmark showing admin approved these

If the permissions show **"⚠️ Consent required"** in yellow, you need to ask your admin to grant consent (or if you're the admin, click "Grant consent" button).

---

## Azure OpenAI Model Deployment

**What to see in Azure Portal (Azure OpenAI → Model Deployments):**

![Azure OpenAI deployment](screenshots/microsoft-foundry-deployment.png)

You should see:
- Model name (e.g., `gpt-4o` or `gpt-4o-mini`)
- Status: **Succeeded** (green)
- Version (the date the model was released)

Click on your deployment to copy the:
- **Deployment name** – Needed for GitHub secret
- **API endpoint** – Needed for GitHub secret

---

## Power Automate Workflow

**What to see in Microsoft Teams (Workflows → Your workflow):**

![Power Automate workflow for Teams](screenshots/power-automate-flow.png)

Your workflow should show:
1. **Trigger:** "When an HTTP request is received"
2. **Action:** "Post adaptive card in a chat or channel"
3. **Configured team and channel** – Your destination

Once saved, look at the trigger details to find your **HTTP webhook URL** (starts with `https://` and ends with a long signature).

---

## Checking Workflow Logs

**After running your workflow, here's what to look for:**

### Success Logs ✅
```
Running on: ubuntu-latest
Checking out code... ✅
Setting up Python... ✅
Installing dependencies... ✅
Fetching announcements... Found 3 new items ✅
Summarizing with AI... ✅
Building Teams cards... ✅
Posting to Teams... ✅
All done!
```

### Error Logs ❌
```
Error: 401 Unauthorized
  This means your secrets are wrong – check them in GitHub Settings
```

To view logs:
1. **Actions** tab → Click your workflow run
2. Click the **"brief_monitor"** job
3. Expand sections to see details
4. Look for ✅ checkmarks (success) or ❌ X marks (errors)

---

## Next Steps

- **See setup details:** [SETUP.md](SETUP.md)
- **Understand the flow:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Monitor and troubleshoot:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

**Any questions about the screenshots?** Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
