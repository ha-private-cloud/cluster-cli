import sys
import tempfile
from pathlib import Path

import click

from cluster_cli.archive import build_tarball
from cluster_cli.authentik import list_users, reset_password
from cluster_cli.client import RunnerClient
from cluster_cli.config import DEFAULT_KUBECONFIG_PATH, load_config
from cluster_cli.deploy import helm_upgrade
from cluster_cli.tagging import default_tag
from cluster_cli.tofu import REPOS, run_tofu


@click.group()
def main():
    """cluster-cli , build apps via cluster-ci's in-cluster runner, deploy
    them locally via helm, and run tofu across this project's repos."""


@main.command()
@click.argument("app_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--namespace",
    required=True,
    help="Target Kubernetes namespace to deploy into (e.g. clusterkeep-dev-pub). No default , state your target environment explicitly.",
)
@click.option(
    "--tag",
    default=None,
    help=(
        "Image tag to build/push. Defaults to a tag derived from APP_DIR's current git "
        "branch , DEV-<timestamp> on dev, PREVIEW-<timestamp> on preview, a plain "
        "<timestamp> on main."
    ),
)
@click.option(
    "--chart",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the app's Helm chart. Defaults to ~/project/charts/<app-name>.",
)
@click.option(
    "--wait/--no-wait",
    default=True,
    help="Stream logs and wait for the result (default), or just enqueue and exit.",
)
@click.option(
    "--deploy/--no-deploy",
    default=True,
    help="Run `helm upgrade` locally after a successful build (default), or just build+push.",
)
def build(app_dir: Path, namespace: str, tag: str | None, chart: Path | None, wait: bool, deploy: bool):
    """Build, test, and push the app in APP_DIR via cluster-ci, then deploy
    it locally with helm (unless --no-deploy).

    APP_DIR must contain a Dockerfile and a pyproject.toml/uv.lock , same
    layout as clusterkeep-ui. Its Helm chart is looked up separately (see
    --chart), not inside APP_DIR.
    """
    try:
        config = load_config()
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    client = RunnerClient(config.runner_url, config.api_token)

    app_name = app_dir.resolve().name
    if tag is None:
        try:
            tag = default_tag(app_dir)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

    with tempfile.TemporaryDirectory() as tmp:
        tarball_path = Path(tmp) / f"{app_name}.tar.gz"
        click.echo(f"Packaging {app_dir} as {app_name}:{tag}...")
        build_tarball(app_dir, tarball_path)

        click.echo("Uploading and queuing build...")
        try:
            result = client.submit_build(app_name, tag, namespace, tarball_path)
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(f"failed to submit build: {exc}") from exc

    build_id = result["build_id"]
    click.echo(f"Build {build_id} queued.")

    if not wait:
        return

    for _event, data in client.stream_logs(build_id):
        click.echo(data)

    final = client.get_build(build_id)
    status = final["status"]
    if status != "succeeded":
        click.secho(f"Build failed at stage '{final.get('stage')}': {final.get('error')}", fg="red")
        sys.exit(1)

    click.secho(f"{app_name}:{tag} built and pushed.", fg="green")

    if not deploy:
        return

    click.echo(f"Deploying {app_name}:{tag} -> {namespace}...")
    try:
        returncode = helm_upgrade(
            app_name=app_name,
            namespace=namespace,
            tag=tag,
            kubeconfig_path=config.kubeconfig_path,
            chart_path=chart,
        )
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if returncode != 0:
        click.secho(f"helm upgrade exited {returncode}", fg="red")
        sys.exit(returncode)

    click.secho(f"{app_name}:{tag} deployed to {namespace}.", fg="green")


@main.command()
@click.option("--app", "app_name", required=True, help="App/image name (also the default chart directory name).")
@click.option("--namespace", required=True, help="Target Kubernetes namespace.")
@click.option("--tag", required=True, help="Image tag to deploy (must already be pushed to the registry).")
@click.option(
    "--chart",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the app's Helm chart. Defaults to ~/project/charts/<app-name>.",
)
def deploy(app_name: str, namespace: str, tag: str, chart: Path | None):
    """Run `helm upgrade` locally for an already-built image tag , no build,
    no cluster-ci involved. Useful for redeploying/rolling back a tag, or
    after a values change to the chart itself."""
    try:
        config = load_config()
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        returncode = helm_upgrade(
            app_name=app_name,
            namespace=namespace,
            tag=tag,
            kubeconfig_path=config.kubeconfig_path,
            chart_path=chart,
        )
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if returncode != 0:
        click.secho(f"helm upgrade exited {returncode}", fg="red")
        sys.exit(returncode)

    click.secho(f"{app_name}:{tag} deployed to {namespace}.", fg="green")


@main.command(context_settings={"ignore_unknown_options": True})
@click.argument("repo", type=click.Choice(REPOS))
@click.option(
    "--tag",
    default=None,
    help="Git tag to check out in REPO before running tofu (fetches tags first). Fails if REPO has uncommitted changes.",
)
@click.argument("tofu_args", nargs=-1, type=click.UNPROCESSED)
def tofu(repo: str, tag: str | None, tofu_args: tuple[str, ...]):
    """Run `tofu <TOFU_ARGS...>` inside REPO's tofu/ directory.

    Everything after REPO is passed straight through to `tofu` as-is, e.g.:

    \b
      cluster-cli tofu cluster-config plan
      cluster-cli tofu clusterkeep-ui apply -var-file=prv.tfvars
      cluster-cli tofu proxmox-tofu output -raw kubeconfig
      cluster-cli tofu cluster-config --tag v1.2.3 plan
    """
    try:
        returncode = run_tofu(repo, tofu_args, tag=tag)
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    sys.exit(returncode)


@main.group()
def auth():
    """Manage Authentik users."""


def _auth_kubeconfig(override: Path | None) -> Path:
    """Resolves a kubeconfig without requiring the CI config.

    `auth` only talks to the cluster, so it must not fail just because
    config.toml (runner URL + API token) has not been set up , that file is
    only needed for build/deploy.
    """
    if override is not None:
        return override
    try:
        return load_config().kubeconfig_path
    except FileNotFoundError:
        return DEFAULT_KUBECONFIG_PATH


_kubeconfig_option = click.option(
    "--kubeconfig",
    "kubeconfig",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Kubeconfig to use. Defaults to config.toml's, else the repo's generated one.",
)


@auth.command("reset-password")
@click.option("--username", required=True, help="Authentik username to reset.")
@click.option(
    "--password",
    default=None,
    help="New password. Omit to be prompted (which keeps it out of your shell history).",
)
@_kubeconfig_option
def auth_reset_password(username: str, password: str | None, kubeconfig: Path | None):
    """Set an Authentik user's password.

    Runs set_password() inside the authentik pod, so Authentik's own hashers
    and password validators apply , this is the same path the admin UI takes,
    not a way around policy.

    \b
      cluster-cli auth reset-password --username test-user
    """
    if password is None:
        password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
    if not password:
        raise click.ClickException("password must not be empty")

    try:
        who = reset_password(username, password, kubeconfig_path=_auth_kubeconfig(kubeconfig))
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.secho(f"Password updated for {who}", fg="green")


@auth.command("list-users")
@_kubeconfig_option
def auth_list_users(kubeconfig: Path | None):
    """List Authentik users."""
    try:
        users = list_users(kubeconfig_path=_auth_kubeconfig(kubeconfig))
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    if not users:
        click.echo("No users found.")
        return
    for user in users:
        status = "" if user["active"] else "  (inactive)"
        click.echo(f"  {user['username']:<20} {user['name'] or '':<24} {user['email'] or ''}{status}")


if __name__ == "__main__":
    main()
