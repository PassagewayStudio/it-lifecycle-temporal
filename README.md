# it-lifecycle-temporal

IT lifecycle automation (offboarding first) built on [Temporal](https://temporal.io), Python SDK.
Lab project: stub activities today, real Okta and Jamf calls next.

## What it does
`OffboardingWorkflow`: suspend Okta user, lock Jamf device, wait for device return
(durable timer), then delete the Okta user. Includes a `status` query.

## Run it locally
```bash
python -m venv env
source env/Scripts/activate        # Git Bash on Windows; macOS/Linux: source env/bin/activate
pip install -r requirements.txt

temporal server start-dev --db-filename temporal.db   # terminal 1  (UI: http://localhost:8233)
python run_worker.py                                  # terminal 2
python run_workflow.py jane.doe@example.com C02TEST12345 30   # terminal 3
```

## Demo: durable execution
1. Start the workflow, then press Ctrl+C in the worker terminal during the timer.
2. Restart the worker. The workflow resumes and finishes; the event history in the UI shows it.

## Tests
`python -m pytest -q` uses Temporal's time-skipping test server, so a 14-day wait runs in seconds.

## Roadmap
- [ ] Real Okta API calls (suspend, revoke sessions, delete)
- [ ] Real Jamf lock command
- [ ] Onboarding, mover and time-boxed access workflows
- [ ] Read-only MCP server (workflow status)
- [ ] Design doc and runbook
