import sys
import tempfile
import time
from pathlib import Path

import click

from ci_cli.archive import build_tarball
from ci_cli.client import RunnerClient
from ci_cli.config import load_config


@click.group()
def main():
    """ci-cli — talk to the in-cluster build/deploy runner (cluster-ci)."""


@main.command()
@click.argument("app_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--namespace",
    required=True,
    help="Target Kubernetes namespace to deploy into (e.g. clusterkeep-dev-pub). No default — state your target environment explicitly.",
)
@click.option("--tag", default=None, help="Image tag to build/push. Defaults to a UTC timestamp.")
@click.option(
    "--wait/--no-wait",
    default=True,
    help="Stream logs and wait for the result (default), or just enqueue and exit.",
)
def build(app_dir: Path, namespace: str, tag: str | None, wait: bool):
    """Build, test, push, and deploy the app in APP_DIR.

    APP_DIR must contain a Dockerfile, a pyproject.toml/uv.lock, and a Helm
    chart under charts/<app-name>/ — same layout as clusterkeep-ui.
    """
    try:
        config = load_config()
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    client = RunnerClient(config.runner_url, config.api_token)

    app_name = app_dir.resolve().name
    tag = tag or time.strftime("%Y%m%d%H%M%S", time.gmtime())

    with tempfile.TemporaryDirectory() as tmp:
        tarball_path = Path(tmp) / f"{app_name}.tar.gz"
        click.echo(f"Packaging {app_dir} as {app_name}:{tag} -> {namespace}...")
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
    if status == "succeeded":
        click.secho(f"{app_name}:{tag} built, pushed, and deployed.", fg="green")
    else:
        click.secho(f"Build failed at stage '{final.get('stage')}': {final.get('error')}", fg="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
