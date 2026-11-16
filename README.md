# cluster-cli

The command line tool behind every ClusterKeep build and deploy. The GitHub workflows on the CI bastion use it, and it works the same from a terminal.

## Setup

```sh
uv sync
uv tool install --editable .
```

Then create `~/.config/cluster-cli/config.toml` like the one below.

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

Packages the app, leaving out anything in its `.gitignore`, and sends it to cluster-ci, which runs the tests and builds and pushes the image. Without `--tag`, the tag comes from the checked-out branch, as shown below.

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

## Shipping a change

Every workflow runs on the self-hosted runners on the CI bastion, because that's the only place besides my own machine with the kubeconfig, the tfvars and this tool's config. The shared workflows themselves are described in the `pipelines` repo.

### Apps

Pushing to `development` deploys to dev, and merging into `preview` deploys to preview. `preview` and `main` only take changes through pull requests. Merging into `main` builds an image without deploying it.

To release, tag `main` and push the tag.

```sh
git checkout main && git pull
git tag v1.2.3
git push origin v1.2.3
```

That builds the `v1.2.3` image. Once that run has passed, open the repo's release workflow in the Actions tab, choose Run workflow and enter the tag. That deploys it to production through the app's OpenTofu `prd` workspace. Always tag from `main`, because the workflow can't tell where a tag came from and ships whatever that commit contains.

To roll back, run the release workflow again with the last good tag. To fix forward, release a new tag.

For a manual `prd` apply, such as an ingress change, pass the current release with `-var image_tag=<tag>`. Otherwise it deploys whatever tag is in `prd.tfvars`, which can roll production back.

### Infrastructure

The infrastructure repos only have `main`. Pushing a `vX.Y.Z` tag plans it automatically, and nothing is applied until I run it by hand.

1. Tag `main` and push the tag.
2. Read the plan in the repo's Actions tab. Take extra care with `proxmox-tofu`, where some changes replace a VM instead of updating it.
3. When it looks right, open the deploy workflow, choose Run workflow and enter the same tag.

The OPNsense firewall in `proxmox-tofu` uses `fw-vX.Y.Z` tags instead, so a normal release never touches it. To roll back an infrastructure change, revert it on `main`, tag again and go through the same steps.

### On the bastion

Nothing keeps the bastion's checkouts up to date between pipeline runs, so run `sync-repos.sh` before using cluster-cli there by hand.

```sh
sync-repos.sh cluster-cli cluster-config
cluster-cli tofu cluster-config --tag v1.0.4 plan
```

Anyone who can SSH into the bastion effectively has cluster admin, because the kubeconfig and tfvars sit there unencrypted.

### Adding a repo

- For an app, copy another app's `build.yml` and `release.yml`, which call the shared workflows.
- For an infrastructure repo, copy another one's `deploy.yml`.
- Add any repo with OpenTofu to `REPOS` in `cluster_cli/tofu.py`.
- Clone it on the bastion with its own read-only deploy key before the first run, as the `pipelines` README explains.

## Technologies

Python 3.13 with Click, requests for cluster-ci's API, and the `tofu`, `helm` and `kubectl` command line tools.
