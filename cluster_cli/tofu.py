import fcntl
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from cluster_cli.config import PROJECT_ROOT

SYNC_LOCK = Path("/tmp/sync-repos.lock")


@contextmanager
def sync_repos_lock():
    """Holds the lock sync-repos.sh takes, so a sync can't reset a repo mid-run."""
    try:
        fd = os.open(SYNC_LOCK, os.O_WRONLY | os.O_CREAT, 0o666)
    except OSError as exc:
        print(f"warning: can't open {SYNC_LOCK} ({exc}), proceeding unlocked", file=sys.stderr)
        yield
        return
    try:
        try:
            os.fchmod(fd, 0o666)
        except OSError:
            pass
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)

# Target name -> (repo directory under ~/project, tofu root within it).
REPOS = {
    "proxmox-tofu": ("proxmox-tofu", "tofu"),
    "proxmox-tofu-firewall": ("proxmox-tofu", "tofu-firewall"),
    "cluster-rbac": ("cluster-rbac", "tofu"),
    "cluster-auth": ("cluster-auth", "tofu"),
    "cluster-config": ("cluster-config", "tofu"),
    "cluster-ci": ("cluster-ci", "tofu"),
    "clusterkeep-ui": ("clusterkeep-ui", "tofu"),
}


def repo_dir(repo: str) -> Path:
    if repo not in REPOS:
        raise ValueError(f"unknown repo {repo!r}. Known repos: {', '.join(REPOS)}")
    return PROJECT_ROOT / REPOS[repo][0]


def repo_tofu_dir(repo: str) -> Path:
    if repo not in REPOS:
        raise ValueError(f"unknown repo {repo!r}. Known repos: {', '.join(REPOS)}")
    dir_name, root = REPOS[repo]
    tofu_dir = PROJECT_ROOT / dir_name / root
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
        ["git", "-C", str(repo_dir), "fetch", "--tags", "--force", "origin"],
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
    """Runs `tofu <args>` with cwd set to REPO's tofu root, streaming output directly."""
    tofu_dir = repo_tofu_dir(repo)
    with sync_repos_lock():
        if tag is not None:
            checkout_tag(repo_dir(repo), tag)
        try:
            result = subprocess.run(["tofu", *args], cwd=tofu_dir)
        except FileNotFoundError as exc:
            raise RuntimeError("`tofu` not found on PATH") from exc
    return result.returncode
