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

GitHub installation access tokens are short-lived. The token request can also
be narrowed to specific repositories and permissions, but it cannot exceed the
repositories or permissions granted to the app installation.

## Local Issue-Write Auth Boundary

The local CLI can use a GitHub App installation token for live issue writes
without changing the control loop.

Install the optional auth dependency when you want local GitHub App token
minting:

```bash
pip install "delegationhq[github-app]"
```

Configure the app outside the repository:

```bash
DELEGATION_GITHUB_APP_CLIENT_ID=<client-or-app-id>
DELEGATION_GITHUB_APP_INSTALLATION_ID=<installation-id>
DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH=<path-to-private-key.pem>
```

You can use `DELEGATION_GITHUB_APP_PRIVATE_KEY` instead of a path when the
environment can hold multiline secrets safely. Literal `\n` sequences are
expanded before signing.

Then choose GitHub App auth on live issue commands:

```bash
delegation apply-issues Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_GITHUB_ISSUES \
  --auth github-app

delegation apply-feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_FEEDBACK_ISSUES \
  --auth github-app
```

The token request uses only issue-write permissions and the repositories
already present in the gated issue drafts. The token is never printed, written
to the ledger, or stored in the repository. Ledger events record only the auth
source, such as `github-app`.

Default `--auth auto` keeps development friendly:

- use configured GitHub App auth when it is available
- otherwise fall back to `GITHUB_TOKEN` or `GH_TOKEN`
- block instead of falling back if GitHub App env vars are present but incomplete
- never mint a token in preview mode

## Local Permission Plan

Use the local planner before building live GitHub App auth:

```bash
delegation github-app-plan --mode read-only
delegation github-app-plan --mode issue-write --repository AmmarAlBalkhi/delegation-bot
delegation github-app-plan --mode actions-control --output .delegation/github-app-plan.json
```

The command does not create a GitHub App, mint a token, call GitHub, or write to
a repository. It gives maintainers a permission plan and installation-token
request shape that can be reviewed before implementation.

Modes:

- `read-only`: metadata, contents, issues, pull requests, actions, and checks
  read access for imported evidence and dashboards.
- `issue-write`: same read access, with issue write access for approved
  feedback drafts.
- `actions-control`: same read access, with actions write access for approved
  workflow dispatch or cancellation.

## CLI And Dashboard UX

Possible future commands:

```bash
delegation doctor --github-app
delegation github-app-plan --mode issue-write
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
