import os
import tarfile
from pathlib import Path

import pathspec

# *.tfstate* must stay: app repos keep live Terraform state next to their source.
ALWAYS_EXCLUDE = [
    ".git/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    ".terraform/",
    "*.tfstate",
    "*.tfstate.*",
]


def _load_spec(app_dir: Path) -> pathspec.PathSpec:
    # .gitignore only: .dockerignore excludes files the deploy stage needs uploaded.
    lines = list(ALWAYS_EXCLUDE)
    gitignore = app_dir / ".gitignore"
    if gitignore.exists():
        lines.extend(gitignore.read_text().splitlines())
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def build_tarball(app_dir: Path, dest: Path) -> Path:
    """Tar+gzip app_dir into dest, excluding anything matched by .gitignore plus ALWAYS_EXCLUDE."""
    app_dir = app_dir.resolve()
    spec = _load_spec(app_dir)

    with tarfile.open(dest, mode="w:gz") as tar:
        for root, dirnames, filenames in os.walk(app_dir):
            root_path = Path(root)
            rel_root = root_path.relative_to(app_dir)

            dirnames[:] = [d for d in dirnames if not spec.match_file(f"{rel_root / d}/")]

            for filename in filenames:
                rel_file = rel_root / filename
                if spec.match_file(str(rel_file)):
                    continue
                tar.add(root_path / filename, arcname=str(rel_file))

    return dest
