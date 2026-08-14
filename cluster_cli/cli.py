import sys
import tempfile
from pathlib import Path

import click

from cluster_cli.archive import build_tarball
from cluster_cli.client import RunnerClient
from cluster_cli.config import load_config
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
@click.argument("tofu_args", nargs=-1, type=click.UNPROCESSED)
def tofu(repo: str, tofu_args: tuple[str, ...]):
    """Run `tofu <TOFU_ARGS...>` inside REPO's tofu/ directory.

    Everything after REPO is passed straight through to `tofu` as-is, e.g.:

    \b
      cluster-cli tofu cluster-config plan
      cluster-cli tofu clusterkeep-ui apply -var-file=prv.tfvars
      cluster-cli tofu proxmox-tofu output -raw kubeconfig
    """
    try:
        returncode = run_tofu(repo, tofu_args)
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    sys.exit(returncode)


if __name__ == "__main__":
    main()
