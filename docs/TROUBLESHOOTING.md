# Troubleshooting 🧯

If something goes wrong, start with the GitHub Actions logs. Most issues are configuration-related.

## Workflow does not run
- Confirm Actions are enabled on the repository.
- Verify the schedule in `.github/workflows/brief-schedule.yml`.
- Run the workflow manually from the Actions tab to validate.

## Missing secrets
- Confirm all secrets listed in [SETUP.md](SETUP.md) exist in the repository.
- Secret names are case-sensitive.

## Microsoft Graph permission errors (401/403)
- Ensure the app registration has Application permissions:
  - `ServiceMessage.Read.All`
  - `ServiceHealth.Read.All`
- Grant admin consent after adding permissions.

## Microsoft Foundry / Azure OpenAI errors
- `AZURE_OPENAI_ENDPOINT` must end with `/`.
- `AZURE_OPENAI_DEPLOYMENT` must match the deployed model name exactly.
- `AZURE_OPENAI_API_VERSION` must be supported by your resource.

## Teams webhook issues
- `TEAMS_WEBHOOK_URL` must be the Teams Workflows HTTP trigger URL.
- If the flow is disabled or deleted, create a new one and update the secret.

## No messages in Teams
- The workflow only posts when new items are found.
- If `NOTIFY_ON_EMPTY` is true, a "no new announcements" card is sent.
- Use the manual workflow run to test and inspect logs.
