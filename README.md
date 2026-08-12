# ci-cli

CLI for `cluster-ci`'s in-cluster build/test/push/deploy runner. Packages an
app directory, uploads it, and streams back the pipeline's progress.

## Setup

```sh
uv sync
uv tool install --editable .   # installs the `ci-cli` command
```

Create `~/.config/ci-cli/config.toml`:

```toml
runner_url = "https://ci.talos.lab"
api_token = "<from `tofu output -raw runner_api_token` in cluster-ci>"
```

Add `ci.talos.lab` to `/etc/hosts`, pointing at a worker node IP (same
pattern as every other `*.talos.lab` host in this project).

## Usage

```sh
ci-cli build ../clusterkeep-ui --namespace clusterkeep-dev-pub
```

`--namespace` is required (no default) — it's the Kubernetes namespace the
deploy stage's `helm upgrade --namespace <target>` runs against, e.g.
`clusterkeep-dev-pub`/`clusterkeep-prv-pub`/`clusterkeep-prd-pub` for
`clusterkeep-ui`. Stating it explicitly on every invocation is deliberate —
no silent default that could deploy to the wrong environment.

`APP_DIR` must contain a `Dockerfile`, `pyproject.toml`/`uv.lock`, and a Helm
chart at `charts/<app-name>/` — same layout as `clusterkeep-ui`. The
directory name becomes the app/image name. Uploads everything except what
`.gitignore` lists plus `.git`, `.venv`, `__pycache__`, `.terraform`, and any
`*.tfstate*` files (always excluded, regardless of `.gitignore` — app repos
keep live Terraform state next to their source). Deliberately does **not**
honor `.dockerignore` for the upload — that file controls what goes into the
built *image* (Kaniko reads it itself once the source is unpacked in the
runner's workspace), which is separate from what needs to be uploaded in the
first place (e.g. `.dockerignore` excludes `charts/`, but the deploy stage
still needs it).
