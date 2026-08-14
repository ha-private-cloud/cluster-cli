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


def checkout_tag(repo_dir: Path, tag: str) -> None:
    """Checks out `tag` in repo_dir (detached HEAD), first refusing a dirty
    tree and re-fetching tags so a stale local tag isn't checked out."""
    status = subprocess.run(
        ["git", "-C", str(repo_dir), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise RuntimeError(f"{repo_dir} has uncommitted changes , refusing to check out {tag!r} over them")

    fetch = subprocess.run(
        ["git", "-C", str(repo_dir), "fetch", "--tags", "origin"],
        capture_output=True,
        text=True,
    )
    if fetch.returncode != 0:
        raise RuntimeError(f"failed to fetch tags in {repo_dir}: {fetch.stderr.strip()}")

    checkout = subprocess.run(
        ["git", "-C", str(repo_dir), "checkout", tag],
        capture_output=True,
        text=True,
    )
    if checkout.returncode != 0:
        raise RuntimeError(f"failed to check out tag {tag!r} in {repo_dir}: {checkout.stderr.strip()}")


def run_tofu(repo: str, args: tuple[str, ...], tag: str | None = None) -> int:
    """Runs `tofu <args>` with cwd set to <repo>/tofu, streaming output directly."""
    tofu_dir = repo_tofu_dir(repo)
    if tag is not None:
        checkout_tag(tofu_dir.parent, tag)
    try:
        result = subprocess.run(["tofu", *args], cwd=tofu_dir)
    except FileNotFoundError as exc:
        raise RuntimeError("`tofu` not found on PATH") from exc
    return result.returncode
