# cluster-cli

CLI for this whole homelab project: builds an app via `cluster-ci`'s in-cluster runner, deploys it locally with `helm` afterward, and wraps `tofu` so you don't have to remember which repo's `tofu/` directory you're supposed to be standing in.

## Setup

```sh
uv sync
uv tool install --editable .   # installs the `cluster-cli` command
```

Create `~/.config/cluster-cli/config.toml`:

```toml
runner_url = "https://ci.talos.lab"
api_token = "<from `tofu output -raw runner_api_token` in cluster-ci>"
# kubeconfig_path = "..."   # optional, defaults to ../proxmox-tofu/_out/kubeconfig
```

Add `ci.talos.lab` to `/etc/hosts`, pointing at a worker node IP (same pattern as every other `*.talos.lab` host in this project).

## `cluster-cli build` , build, push, and deploy

```sh
cluster-cli build ../clusterkeep-ui --namespace clusterkeep-dev-pub
```

`--namespace` is required (no default) , no silent default that could deploy to the wrong environment. `APP_DIR` must contain a `Dockerfile` and `pyproject.toml`/`uv.lock` (its Helm chart is looked up separately, see below). Uploads everything except what `.gitignore` lists plus `.git`, `.venv`, `__pycache__`, `.terraform`, and any `*.tfstate*` files (always excluded, regardless of `.gitignore`).

Without `--tag`, the tag is derived from `APP_DIR`'s currently checked-out git branch , `dev` → `DEV-<UTC timestamp>`, `preview` → `PREVIEW-<UTC timestamp>`, `main` → a plain `<UTC timestamp>` (no prefix). Any other branch fails with an error asking for an explicit `--tag`. This prefix is what `clusterkeep-ui`'s Tofu (`image_tag_prefix`) filters the registry on per environment when it auto-selects the latest tag to deploy , see its README.

This: packages and uploads `APP_DIR` to `cluster-ci`'s runner, which tests, builds, and pushes the image; then, once that succeeds, runs `helm upgrade --install --reuse-values --set image.tag=<tag>` **locally** against the app's chart. Pass `--no-deploy` to only build+push, or `--no-wait` to just enqueue the build and exit without deploying at all.

## `cluster-cli deploy` , redeploy without building

```sh
cluster-cli deploy --app clusterkeep-ui --namespace clusterkeep-dev-pub --tag 20260812160204
```

Runs the same local `helm upgrade` step `build` does, for an image tag that's already been pushed , useful for rolling back to a previous tag, or re-applying after editing the chart itself.

Both commands look for the chart at `~/project/charts/<app-name>` by default (deliberately outside every git repo , see `--chart` to override). That path needs a real `tofu`/`helm`/kubeconfig on whatever machine runs `cluster-cli`; it isn't handled by any in-cluster Job , that's why the GitHub Actions self-hosted runner in `../proxmox-tofu`'s "CI bastion" exists, rather than trying to run `cluster-cli` from GitHub's own hosted runners (which have no route to `*.talos.lab`).

## `cluster-cli tofu` , run tofu in the right directory

```sh
cluster-cli tofu cluster-config plan
cluster-cli tofu clusterkeep-ui apply -var-file=prv.tfvars
cluster-cli tofu proxmox-tofu output -raw kubeconfig
```

Every arg after the repo name is passed straight through to `tofu`, with `cwd` set to that repo's `tofu/` directory , this is a thin convenience wrapper, not a reimplementation of tofu's CLI. Valid repo names: run `cluster-cli tofu --help` to see the current list (kept in `cluster_cli/tofu.py`, one entry per repo under `~/project` that has a `tofu/` subdirectory).
