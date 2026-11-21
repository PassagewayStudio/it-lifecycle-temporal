# it-lifecycle-temporal: Design Doc and Runbook

Nov 20, 2026 · @Carlos

## Summary

it-lifecycle-temporal automates two IT workflows on Temporal (Python SDK): offboarding a user and granting time-boxed access. Both run against an Okta developer tenant, and every step survives worker restarts because Temporal records progress durably.

What is real: Okta suspend, session clear, delete, and group add/remove, each tested against a dev tenant and against mocked HTTP. What is stubbed: the Jamf device lock, because no managed device was available for the lab. This is a lab project on a local dev server, not a production deployment.

An AI assistant can also check on the workflows through a read-only MCP server, tested live against the dev server.

## Problem and goals

Offboarding and access changes are multi-step, touch several systems, and fail halfway: an API rate limit, a missed return of a laptop, an approval that never comes. Done by hand or in a chain of scripts, a half-finished offboarding is easy to miss and hard to audit.

Goals:

- Every step runs to completion or fails visibly, with no silent half-finished state.
- Waiting (for a device return, for an approval, for access to expire) costs nothing and survives restarts.
- Retries are safe: running a step twice must not cause harm.
- Destructive steps are guarded, and the full history of each request is inspectable.

Non-goals for this lab: HR system integration, a production deployment, and managing real devices.

## Architecture

&#91;embedded content: architecture · 4 parts, worker is the only caller of Okta\]

Temporal stores each request's progress and timers, so the worker can be stopped and restarted without losing a request. The worker is the only part that calls Okta, and it does so only through activities.

A read-only MCP server (see below) connects to Temporal the same way the command-line scripts do, but can only list and query workflows.

## Workflows

Two workflows share one task queue (`off``boarding-task-queue`) and one worker. Workflow IDs include the user's email, so only one run per user can be active at a time.

**OffboardingWorkflow**

| Step | Activity | Status | If it fails |
| --- | --- | --- | --- |
| 1. Suspend account, clear sessions | `suspend_okta_user` | Real | Retries up to 5 times; a missing user or a bad token fails at once |
| 2. Lock the laptop | `lock_jamf_device` | Stub | Retries up to 5 times |
| 3. Wait for device return | durable timer (30 s in the lab, days in real use) | Real | Survives worker and server restarts |
| 4. Delete the account | `delete_okta_user` | Real, opt-in | Fails at once unless `OKTA_ALLOW_DELETE=true` |

A `status` query reports the current step without changing anything.

**AccessRequestWorkflow**

| Step | Mechanism | If it fails or is skipped |
| --- | --- | --- |
| 1. Wait for a decision | `approve` or `deny` signal; first decision wins | No decision within the timeout: request expires, nothing granted |
| 2. Grant access | `grant_okta_group_access` (add to an Okta group) | Retries up to 5 times |
| 3. Hold the access | durable timer, ended early by `revoke_now` | Survives restarts |
| 4. Remove access | `revoke_okta_group_access` | Always runs after the timer or early revoke |

## Reliability

- **Durable timers.** The device-return wait and the access window are Temporal timers, not sleeping processes. Killing the worker mid-wait and restarting it resumes the workflow where it left off; this was demonstrated live and is the main reason to use Temporal here.
- **Idempotent activities.** Suspending an already-suspended user returns "already-suspended"; deleting a missing user returns "already-deleted"; group add and remove are safe to repeat. A retry after a half-finished call never causes harm.
- **Two kinds of failure.** Rate limits (429) and server errors raise a normal error, so Temporal retries with backoff (1 s growing to 30 s, up to 5 attempts). Bad token, missing user, a user in a state that cannot be suspended, or delete not enabled raise a non-retriable error and fail the workflow immediately, because retrying cannot fix them.
- **Cleanup always runs.** The access-request workflow removes group access after the timer or an early revoke, whichever comes first.
- **Tests.** Workflow tests use Temporal's time-skipping test server, so a 14-day wait runs in about a second. Okta calls are tested against a mocked HTTP transport, so nothing touches a tenant during tests. 13 tests pass.

## Read-only MCP server

`mcp_server.py` lets an AI assistant answer "what step is this offboarding on?" and "why is it stuck?". It reads from Temporal and can change nothing.

| Tool | What it returns |
| --- | --- |
| `list_workflows` | Workflows by status (Running by default), with ID, type and start time |
| `get_workflow_status` | The status plus the current step, taken from the workflow's `status` query |
| `diagnose_workflow` | Pending activities, retry counts and last failures, plus plain-English hints |

- **Read-only by design.** All three tools are marked read-only. There are no signal, terminate or start tools, and the server never calls Okta, so it needs no Okta token. Any future write tool belongs behind human approval.
- **Worker-down detection.** If a workflow does not answer the status query within 5 seconds, the tools report the step as unavailable and the diagnosis says the worker is probably not running.
- **Tested live.** Connected to Claude Desktop against the dev server, it described a healthy 300-second device-return wait, reported the step as unavailable while the worker was stopped, and returned to normal after the worker restarted.
- **Limit.** It cannot tell a stopped worker from one that is restarting, so a single "unavailable" reading is a prompt to check the worker, not proof it is down.

## Security and controls

- **Secrets.** The Okta org URL and API token live in a `.env` file that is gitignored, never in code or screenshots. `.env.example` documents the variables without values.
- **Least privilege.** The API token inherits its admin's permissions, so it should belong to an admin role limited to user lifecycle and group changes, not a super admin. In a production setup this would be a dedicated service account with a rotation schedule.
- **Destructive step guarded.** Permanent deletion does nothing unless `OKTA_ALLOW_DELETE=true` is set, and fails with a clear, non-retriable error otherwise. This protects against a typo or a wrong `.env` deleting a real account.
- **Test users only.** Every live run in this lab used throwaway users. The admin account was never a target.
- **Audit trail.** Temporal keeps a full event history per workflow: who approved, when each activity ran, and each retry. That history is the record of what happened to an account.
- **Not yet covered.** The local dev server has no authentication. A real deployment would use Temporal Cloud or a secured self-hosted cluster, and would require approvers to be authenticated.

## Build vs buy

Use a low-code tool for short, single-system tasks; use Temporal when a process waits for days, needs approvals, spans systems, and must be tested and audited. The earlier joiner/leaver flow in this portfolio was built in n8n; offboarding was rebuilt on Temporal for durable timers and real tests. Okta Workflows was not tried hands-on in this lab, so that column is an assessment, not experience.

| Question | Temporal | n8n | Okta Workflows |
| --- | --- | --- | --- |
| Where the logic lives | Code in git, reviewed like any other change | Visual flow in the editor, exportable | Visual flow inside Okta |
| Testing | Unit tests, including time-skipping for long waits | Manual test runs | Not tested in this lab |
| Long waits and approvals | Durable timers and signals are core features | Wait nodes exist; not used for multi-day waits here | Not tested in this lab |
| Failure handling | Per-activity retry policy, non-retryable errors, full history | Retry settings per node, execution log | Not tested in this lab |
| Who can maintain it | Engineers who read Python | Technical admins, low barrier | Admins, closest to Okta itself |
| What you run | A Temporal service and a worker you host | An n8n instance (self-hosted in this portfolio) | Hosted by Okta; check licensing |
| Best fit | Long-running, multi-step, auditable processes | Quick integrations and notifications | Automations that stay inside Okta |

## Runbook

Start with the workflow ID, which is `offboard-<email>` or `access-<email>`. Open the Temporal UI (http://localhost:8233 for the dev server) or use the CLI below, and read the event history before changing anything.

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| Workflow is Running but nothing moves | The worker is not running, so no one is polling the task queue | Run `temporal task-queue describe` to confirm no pollers, then start `python run_worker.py`. The workflow resumes by itself. |
| An activity keeps retrying (attempt count climbs) | Okta rate limit (429), an Okta outage, or a network problem | Read the last failure in the UI or `describe`. Retries back off up to 30 s and stop after 5 attempts. Wait out a rate limit; fix the network if that is the cause. |
| Failed at the suspend or lookup step with 401 or 403 | The API token is wrong, expired, or its admin role is too narrow | Fix the token or role in `.env`, restart the worker, then start the workflow again. Suspend is safe to repeat. |
| Failed with "Okta delete is disabled" | `OKTA_ALLOW_DELETE` is not `true` (this is the safety switch working) | Enable it only for a throwaway user, restart the worker, and start the offboarding again. |
| Failed with "Cannot suspend ... status is X" | The user is already deprovisioned or never activated | Check the user in the Okta admin console. There is nothing to suspend; handle any remaining steps manually. |
| Access request sits at "waiting for approval" | No one has decided | Send an `approve` or `deny` signal, or let the request expire after its timeout. |
| User is still in the group after a failure or a terminate | The revoke step did not run | Remove the user from the group in the Okta admin console and confirm. A terminated workflow does no cleanup. |
| Starting a workflow says it is already running | Only one run per user is allowed at a time | `describe` the existing run, then signal it, wait for it, or terminate it. |

Commands (check `temporal workflow --help` if flags differ in your CLI version):

```bash
temporal workflow list --query 'ExecutionStatus="Running"'
temporal workflow describe --workflow-id offboard-jane.doe@example.com
temporal workflow show     --workflow-id offboard-jane.doe@example.com
temporal workflow query    --workflow-id offboard-jane.doe@example.com --type status
temporal workflow signal   --workflow-id access-jane.doe@example.com --name approve --input '"manager"'
temporal workflow signal   --workflow-id access-jane.doe@example.com --name revoke_now
temporal workflow terminate --workflow-id access-jane.doe@example.com --reason "stuck, handled manually"
temporal task-queue describe --task-queue offboarding-task-queue
```

Terminate is a last resort: it stops the workflow immediately and runs no cleanup, so always check Okta afterwards for leftover group membership or a half-suspended account.

## Limits and next steps

Known limits:

- The Jamf device lock is a stub; no managed device was available, so it is tested only as a placeholder.
- The Temporal dev server has no authentication and is not highly available.
- There is no HR system feeding events in; requests start from a command-line script.
- Approvals come from a signal sent by script, not from an authenticated approver in Slack.

Next steps, in the order I would take them:

1. Write actions for the MCP server, such as sending an approve signal, only with authenticated approvers and human confirmation.
2. A real Jamf lock once a managed device is available.
3. Onboarding and mover workflows that reuse the same activities.
4. Slack approvals, and Okta group setup managed with Terraform.
