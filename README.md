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

## Access requests (time-boxed access)
`AccessRequestWorkflow`: a request waits for a manager's approval (signal), adds the user to an
Okta group, keeps the access for a set time on a durable timer, then removes it. An unanswered
request expires, and `revoke` ends access early.

```bash
python run_access_request.py request jane.doe@example.com <okta_group_id> 120
python run_access_request.py approve jane.doe@example.com manager
python run_access_request.py status  jane.doe@example.com
```

## MCP server (read-only)
`mcp_server.py` lets an AI assistant check on workflows. Tools: `list_workflows`,
`get_workflow_status` and `diagnose_workflow` (pending activities, retries, worker down?).
It only reads from Temporal, with no signal, terminate or start tools, and it never touches Okta.
Any future write tool should sit behind human approval.

```bash
python mcp_server.py        # stdio; normally launched by the MCP client, not by hand
```

## Status
- Okta: suspend + session clear (real, tested against a dev tenant), group add/remove (real)
- Okta delete (real, deactivate then delete): disabled unless `OKTA_ALLOW_DELETE=true` in `.env`; use a throwaway user only
- Jamf lock: stub (no managed Mac available for the lab)

## Roadmap
- [x] Real Okta suspend and session clear
- [x] Time-boxed access workflow (approval signal, timer, auto-revoke)
- [x] Real Okta delete (behind an opt-in flag)
- [ ] Real Jamf lock command (needs a managed device)
- [ ] Onboarding and mover workflows
- [x] Read-only MCP server (workflow status and diagnosis)
- [x] Design doc and runbook (docs/)
