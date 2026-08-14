import subprocess
from pathlib import Path

from cluster_cli.config import DEFAULT_CHARTS_DIR


def chart_path_for(app_name: str, chart_path: Path | None) -> Path:
    path = chart_path or (DEFAULT_CHARTS_DIR / app_name)
    if not path.is_dir():
        raise ValueError(
            f"chart not found at {path} , pass --chart, or check it was moved to {DEFAULT_CHARTS_DIR}"
        )
    return path


def helm_upgrade(
    *, app_name: str, namespace: str, tag: str, kubeconfig_path: Path, chart_path: Path | None = None
) -> int:
    """Runs `helm upgrade --install` locally against the app's chart, bumping
    only image.tag and reusing whatever values Tofu's helm_release already
    set (ingress host, chart version, etc). Streams helm's own output
    directly rather than capturing it."""
    resolved_chart = chart_path_for(app_name, chart_path)
    args = [
        "helm",
        "upgrade",
        "--install",
        app_name,
        str(resolved_chart),
        "--namespace",
        namespace,
        "--kubeconfig",
        str(kubeconfig_path),
        "--reuse-values",
        "--set",
        f"image.tag={tag}",
    ]
    try:
        result = subprocess.run(args)
    except FileNotFoundError as exc:
        raise RuntimeError("`helm` not found on PATH") from exc
    return result.returncode
