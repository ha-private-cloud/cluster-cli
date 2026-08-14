import subprocess
from pathlib import Path

from cluster_cli.config import PROJECT_ROOT

# Every repo under ~/project whose .tf files live in a tofu/ subdirectory.
REPOS = [
    "proxmox-tofu",
    "cluster-rbac",
    "cluster-auth",
    "cluster-config",
    "cluster-ci",
    "clusterkeep-ui",
]


def repo_tofu_dir(repo: str) -> Path:
    if repo not in REPOS:
        raise ValueError(f"unknown repo {repo!r}. Known repos: {', '.join(REPOS)}")
    tofu_dir = PROJECT_ROOT / repo / "tofu"
    if not tofu_dir.is_dir():
        raise ValueError(f"{tofu_dir} doesn't exist")
    return tofu_dir


def run_tofu(repo: str, args: tuple[str, ...]) -> int:
    """Runs `tofu <args>` with cwd set to <repo>/tofu, streaming output directly."""
    tofu_dir = repo_tofu_dir(repo)
    try:
        result = subprocess.run(["tofu", *args], cwd=tofu_dir)
    except FileNotFoundError as exc:
        raise RuntimeError("`tofu` not found on PATH") from exc
    return result.returncode
