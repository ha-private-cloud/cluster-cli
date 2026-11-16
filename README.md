# cluster-cli

The command line tool behind every ClusterKeep build and deploy. The GitHub workflows on the CI bastion use it, and it works the same from a terminal.

## Setup

```sh
uv sync
uv tool install --editable .
```

Then create `~/.config/cluster-cli/config.toml`:

```toml
runner_url = "<cluster-ci runner address>"
api_token = "<runner_api_token output from cluster-ci>"
```

`kubeconfig_path` is optional and defaults to `../proxmox-tofu/_out/kubeconfig`. Every repo is expected to sit next to each other in `~/project`.

## Commands

### `cluster-cli build`

```sh
cluster-cli build ../storage-ui --namespace storage-dev-pub --no-deploy
```

Packages the app, leaving out anything in its `.gitignore`, and sends it to cluster-ci, which runs the tests and builds and pushes the image. Without `--tag`, the tag comes from the checked-out branch:

| Branch | Tag |
|---|---|
| `development` | `DEV-<timestamp>` |
| `preview` | `PREVIEW-<timestamp>` |
| `main` | `<timestamp>` |

Release tags are `vX.Y.Z`, passed with `--tag`. Without `--no-deploy` it also runs a Helm upgrade afterwards, though the workflows always deploy through OpenTofu instead.

### `cluster-cli deploy`

```sh
cluster-cli deploy --app storage-ui --namespace storage-dev-pub --tag DEV-20261116201321
```

Runs a Helm upgrade for an image that's already been pushed, changing only the image tag. It can't install an app for the first time, because the production settings live in OpenTofu.

### `cluster-cli tofu`

```sh
cluster-cli tofu cluster-config plan
cluster-cli tofu storage-api apply -var-file=prv.tfvars
cluster-cli tofu auth-api --tag v0.5.0 plan
```

Runs `tofu` in the right repo's `tofu/` folder and passes every other argument straight through. `--tag` checks that tag out first and refuses if the repo has uncommitted changes. A lock stops a repo sync running at the same time. The repos it knows about are proxmox-tofu, proxmox-tofu-firewall, cluster-auth, cluster-config, cluster-ci, clusterkeep-ui, auth-api, storage-ui, admin-ui and storage-api, set in `cluster_cli/tofu.py`.

### `cluster-cli auth`

```sh
cluster-cli auth list-users
cluster-cli auth reset-password --username someone
```

Runs auth-api's admin command inside its production pod, for when admin-ui isn't an option. The password goes in over standard input so it never shows up in the process list. A reset ends that person's sessions, and they have to choose a new password at their next login.

## Technologies

Python 3.13 with Click, requests for cluster-ci's API, and the `tofu`, `helm` and `kubectl` command line tools.
