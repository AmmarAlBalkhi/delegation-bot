# GitHub App Installation Design

DelegationHQ can start with local tokens, but a public product should
eventually use a GitHub App for scoped repository access.

Simple version:

```text
User installs app.
App gets narrow permissions.
DelegationHQ dry-runs first.
Live writes need explicit approval.
Ledger records proof.
```

## Why A GitHub App

A GitHub App fits DelegationHQ better than asking users for broad personal
tokens:

- installations can be limited to selected repositories
- permissions can be narrower and easier to explain
- webhooks can notify the control plane about repository events
- installation tokens can be short-lived
- hosted dashboard work can separate user identity from app automation

The app should not become a hidden executor. It should be an authenticated
transport for the same control-plane loop:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

## Installation Modes

### Read-Only Mode

Use this first.

Purpose:

- inspect Harnessfiles
- read issues and pull requests
- read workflow status
- show ledger and eval status in a dashboard

No live writes.

### Issue-Write Mode

Use this for the first narrow live action.

Purpose:

- create or update GitHub Issues from approved feedback drafts
- write backlinks to run evidence
- record the resulting issue number and URL in the ledger

Still no code changes, package publishing, workflow dispatch, or model calls.

### Future Write Modes

These should require separate design review:

- pull request comments
- branch creation
- workflow dispatch
- repository file writes
- release creation
- deployment actions

## Minimum Permissions

Start with least privilege. Do not ask for a permission until a specific feature
needs it.

### Read-Only Install

- Metadata: read
- Contents: read, only if the app needs to read Harnessfiles from the repo
- Issues: read
- Pull requests: read
- Actions: read, only if workflow run evidence is shown
- Checks: read, only if check status is shown

### Issue-Write Install

Everything from read-only mode, plus:

- Issues: read and write

Reason: the first live action is creating or updating GitHub Issues from
approved, previewed drafts.

## First Webhook Events

Start small:

- `installation`
- `installation_repositories`
- `issues`
- `issue_comment`
- `pull_request`
- `workflow_run`
- `check_run` or `check_suite` only when check evidence is needed

Webhook handling should append or reference ledger evidence. It should not grant
agents more autonomy by itself.

## Authentication Shape

The future hosted service should:

1. Store the GitHub App private key outside the repository.
2. Create a signed app JWT server-side.
3. Exchange it for an installation access token.
4. Use the installation token only for the selected repository and feature.
5. Record what was read or written in the run ledger.

The local CLI can continue supporting `GITHUB_TOKEN` for development. The app
path should be added when the hosted or team workflow needs it.

## CLI And Dashboard UX

Possible future commands:

```bash
delegation doctor --github-app
delegation app permissions
delegation app preview-install
```

Hosted dashboard flow:

1. User picks a repository.
2. User chooses read-only or issue-write mode.
3. Dashboard explains permissions in plain language.
4. Dashboard shows the next dry-run command or imported run ledger.
5. Any live write still requires an explicit apply action.

## Safety Rules

- Dry-run remains the default.
- A GitHub App token does not bypass policy gates.
- Live issue writes still require explicit confirmation.
- Every live write must create ledger evidence.
- The app should request repository access only where installed.
- Broad permissions need a decision-log entry before implementation.
- Webhooks should not trigger unbounded agent execution.

## References

- GitHub Apps can be installed on accounts or organizations and granted access
  to specific repositories: https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/about-creating-github-apps
- GitHub App permissions should be selected with least privilege:
  https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app
- GitHub Apps can receive webhook events for repositories they can access:
  https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/using-webhooks-with-github-apps
- Installation access tokens are the server-to-server auth path:
  https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation
