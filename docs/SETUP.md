# Setup Guide 🧭

This step-by-step guide will get you up and running in about **20-30 minutes**.

---

## 📋 Overview: What You'll Do

This guide has 5 main setup steps:

1. **Clone the repository** → Get the code on your computer
2. **Set up Microsoft Foundry** → Create the AI summarization engine
3. **Create Teams webhook** → Tell the app where to send messages
4. **Register your app** → Give the app permission to read Message Center
5. **Add GitHub secrets** → Securely store all your credentials

Let's go! 👇

---

## Step 1: Clone the Repository 📥

First, get a copy of the code.

### Option A: Using Git (Recommended)

If you have Git installed, open your terminal or PowerShell:

```bash
# Clone the repository
git clone https://github.com/rashadbakirov/MS-Message-Center-Monitor.git

# Go into the folder
cd MS-Message-Center-Monitor

# (Optional) Open in Visual Studio Code
code .
```

### Option B: Using GitHub Web Interface

1. Go to https://github.com/rashadbakirov/MS-Message-Center-Monitor
2. Click **Code** → **Download ZIP**
3. Extract the ZIP file to a folder on your computer
4. Open that folder in your terminal or Visual Studio Code

### Want Your Own Version?

If you want to maintain your own fork (recommended for teams):

1. Click the **Fork** button at the top right of the GitHub repo
2. Clone your fork instead: `git clone https://github.com/YOUR-USERNAME/MS-Message-Center-Monitor.git`

---

## Step 2: Set Up Microsoft Foundry (Azure OpenAI) 🤖

This is where the AI magic happens – your announcements will be summarized here.

### What is Microsoft Foundry?
Microsoft Foundry (also called Azure OpenAI) is Azure's managed service for running AI models like GPT-4o. It's the "brain" that reads your announcements and creates summaries.

### 📝 Choose Your Setup Method

**Option A: Microsoft Foundry (Fastest) ⭐**

1. Go to [ai.azure.com](https://ai.azure.com) in your browser
2. Sign in with your Azure account
3. Click **Create deployment**
4. Select your model:
   - **Recommended:** `GPT-4o`
   - **Budget:** `gpt-4o-mini`
5. Complete the setup and copy the credentials shown

![Microsoft Foundry deployment](../../docs/screenshots/microsoft-foundry-deployment.png)

**Option B: Azure Portal**

1. Open [Azure Portal](https://portal.azure.com)
2. Search for **"Azure OpenAI"** → **Create new resource**
3. Fill in:
   - **Resource group:** Create new or existing
   - **Name:** e.g., `message-center-ai`
   - **Region:** Choose your region
   - **Pricing tier:** Standard (S0)
4. Click **Create** and wait
5. Once created, click **Go to resource**
6. Click **Model deployments** → **Create new deployment**
7. Select your model and deploy

**Option C: Visual Studio Code (For Developers)**

1. Install [Azure AI Toolkit](https://marketplace.visualstudio.com/items?itemName=ms-windows-ai-studio.windows-ai-studio)
2. Connect to your Azure subscription from VS Code
3. Create/view your deployments in the extension
4. Copy credentials directly

### 📋 Copy Your Credentials

Whichever method you chose, you need these values:

```
AZURE_OPENAI_ENDPOINT = https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY = (Your primary or secondary key)
AZURE_OPENAI_DEPLOYMENT = gpt-4o (or gpt-4o-mini if you chose that)
AZURE_OPENAI_API_VERSION = 2024-10-21
```

Save these to a notepad – you'll add them to GitHub in Step 5.

---

## Step 3: Create Teams Webhook (Power Automate Workflow) 💬

This tells the app where to send your announcement cards to Teams.

### What is a Webhook?
A webhook is a special URL that acts like a mailbox – when the app sends a message to this URL, Teams receives it and posts it to your channel.

### 🔗 Create the Webhook

1. Open **Microsoft Teams** (web or desktop)
2. Go to the **channel** where you want announcements
3. Click **⋯** (three dots at the top right) → **Workflows**
4. Click **Send webhook alerts to a channel**
5. Name: `Message Center Monitor`
6. Click **Create**

![Power Automate workflow](../../docs/screenshots/power-automate-flow.png)

### 💾 Copy the Webhook URL

1. After creating, you'll see the **webhook URL**
2. **Copy this entire URL** – it's your `TEAMS_WEBHOOK_URL`
3. Save it to your notepad

The URL looks like:
```
https://prod-XX.environment.api.powerplatform.com/webhooks/...
```

⚠️ **Important:** Treat this URL like a password. Anyone with it can post to your channel. Only use it in GitHub secrets.

---

## Step 4: Register Your App (Azure App Registration) 🔐

This gives the app permission to read your Message Center announcements.

### What is App Registration?
An app registration is like a digital identity for your app. It allows your Python script to prove it's authorized to read Microsoft 365 data.

### 📝 Create the App Registration

1. Open [Azure Portal](https://portal.azure.com)
2. Search for **"App registrations"** at the top
3. Click **New registration**
4. Fill in:
   - **Name:** `Microsoft Message Center Monitor`
   - **Supported account types:** `Accounts in this organizational directory only`
5. Click **Register**

### ✅ Add Microsoft Graph Permissions

Now you'll give this app permission to read your Message Center.

1. You're now in your new app registration
2. In the left menu, click **API permissions**
3. Click **Add a permission**
4. Search for **"Microsoft Graph"** → Select it
5. Choose **Application permissions** (not Delegated)
6. Search for `ServiceMessage` and check **ServiceMessage.Read.All**
7. Search for `ServiceHealth` and check **ServiceHealth.Read.All**
8. Click **Add permissions**

![App registration permissions](../../docs/screenshots/app-registration-permissions.png)

### 👤 Grant Admin Consent

1. Still in **API permissions**
2. Look for a button saying **"Grant admin consent for [Your Org]"**
3. Click it and confirm
4. You should see a green checkmark next to your permissions

### 🔑 Create a Client Secret

1. In the left menu, click **Certificates & secrets**
2. Click **+ New client secret**
3. **Description:** `GitHub Actions`
4. **Expires:** Choose 24 months or longer
5. Click **Add**
6. **Immediately copy the secret value** (you can't see it again!)
7. Save it to your notepad as `MC_CLIENT_SECRET`

### 📋 Copy Your App IDs

Still in your app registration:

1. Click **Overview** in the left menu
2. Copy these values to your notepad:

```
MC_APP_ID = (Application (client) ID)
AZURE_TENANT_ID = (Directory (tenant) ID)
```

👉 **Screenshot:** Check `app-registration-permissions.png` for what the permissions should look like

---

## Step 5: Add GitHub Secrets 🔒

Now you'll securely store all your credentials in GitHub so the workflow can use them.

### Why Secrets?
Secrets are encrypted values that only your GitHub Actions workflow can read. They're never visible in logs or code.

### 🔑 Add Each Secret

1. Go to your GitHub repository
2. Click **Settings** (top menu)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**

**Add these 8 secrets one by one:**

| Secret Name | Value | From Where |
|------------|-------|-----------|
| `AZURE_TENANT_ID` | Directory ID | Azure App Registration → Overview |
| `MC_APP_ID` | Application ID | Azure App Registration → Overview |
| `MC_CLIENT_SECRET` | Your secret value | Azure App Registration → Certificates & secrets |
| `AZURE_OPENAI_ENDPOINT` | Your endpoint | Azure OpenAI → Keys and endpoints |
| `AZURE_OPENAI_API_KEY` | Key 1 | Azure OpenAI → Keys and endpoints |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name | Azure OpenAI (gpt-4o or gpt-4o-mini) |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | Fixed value (copy as-is) |
| `TEAMS_WEBHOOK_URL` | Your webhook URL | Power Automate workflow → HTTP URL |

**Example of adding a secret:**
```
1. Click "New repository secret"
2. Name: AZURE_TENANT_ID
3. Value: (paste your tenant ID)
4. Click "Add secret"
```

Repeat for all 8 secrets.

### ✅ Verify (Optional)

If you want to double-check, open the `.env.example` file in your repository – it shows all the variables you need to add.

---

## ✨ You're Done!

All your credentials are now securely stored. Time to test it!

👉 **Next step:** Go to [DEPLOYMENT.md](DEPLOYMENT.md) to run your first workflow and see the magic happen.

1. Go to the GitHub Actions tab.
2. Open "Microsoft Message Center Monitor (Scheduled)".
3. Click "Run workflow".
4. Confirm a card shows up in Teams.

## Optional settings

You can customize behavior with these optional variables:
- `DAILY_BRIEF_LOOKBACK_HOURS` (default: 24)
- `NOTIFY_ON_EMPTY` (default: true)
