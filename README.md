# tap-argocd

Singer tap for [Argo CD](https://argo-cd.readthedocs.io/). It reads the Argo CD REST API and emits:

| stream | replication | key | what |
|---|---|---|---|
| `applications` | full table | `uid` | current state of every application: sources, destination, sync/health status, running images, ApplicationSet owner |
| `syncs` | incremental on `finished_at`, bookmarked per application | `id` | one row per sync operation (a deploy attempt), successful or failed |

Both streams come from a single `GET /api/v1/applications` call per run.

## How `syncs` is built

Argo CD doesn't expose a sync log. Each application carries:

- `status.history`: successful syncs only, capped by `revisionHistoryLimit` (default 10)
- `status.operationState`: the latest operation, including failures, until the next one replaces it

The tap merges the two into one row per operation, keyed on `<app uid>:<operation start>`.

- **Backfill depth:** the first run can only go back as far as each app's history limit.
- **Failed syncs:** these are only visible until the app's next sync, so run the tap more often than apps deploy (every 10–15 minutes).
- **Running operations:** skipped, and emitted once they finish.
- **Dry runs:** included, with `dry_run = true`.

## Config

```json
{
  "base_url": "https://argocd.example.com",
  "token": "<argo cd api token>",
  "start_date": "2026-01-01T00:00:00Z",
  "projects": "default, payments",
  "selector": "env=prod",
  "verify_ssl": true,
  "request_timeout": 300
}
```

`projects`, `selector`, `verify_ssl` and `request_timeout` are optional.

To create a read-only token, add a local account with the `apiKey` capability in `argocd-cm`:

```yaml
accounts.bilanc: apiKey
```

Grant it read access in `argocd-rbac-cm`:

```csv
p, role:bilanc-readonly, applications, get, */*, allow
g, bilanc, role:bilanc-readonly
```

Then generate the token:

```bash
argocd account generate-token --account bilanc
```

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/tap-argocd --config config.json --discover > catalog.json
.venv/bin/tap-argocd --config config.json --catalog catalog.json --state state.json
.venv/bin/pytest tests
```

## Local Argo CD

A throwaway cluster to test against:
- kind cluster `argocd`
- Argo CD `stable`
- read-only `bilanc` account
- sample apps from `argoproj/argocd-example-apps`

```bash
~/.local/bin/argocd-port-forward &          # https://localhost:8080 (restarts if the forward drops)
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d   # UI: admin / this
argocd login localhost:8080 --username admin --insecure --grpc-web
argocd account generate-token --account bilanc   # token for config.json, with "verify_ssl": false
argocd app sync guestbook-prod --revision <sha>  # add history; broken-prod always fails
kind delete cluster --name argocd                # tear down
```

## Mapping to Bilanc models

- **`int_workflow_runs`:** one `syncs` row = one run.
  - `workflow_name` = `app_name`
  - `head_sha` = `revision`
  - `run_conclusion`: `phase` Succeeded → success, Failed/Error → failure
  - `trigger_event`: `initiated_by_automated` → push, otherwise workflow_dispatch
- **`int_deployment_events`:** a `syncs`-based `argocd_sync` signal, restricted to production apps (by destination or app name).
  - Skip apps with `manages_applications` (app-of-apps parents).
  - Skip `dry_run` rows.
- **Repository:** `sources[].repo_url` is often a GitOps config repo, not the code repo. Map the app to its code repository using, in order of preference:
  1. A rule
  2. An annotation
  3. `applications.images`
