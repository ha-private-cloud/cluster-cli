import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "cluster-cli" / "config.toml"

# cluster-cli lives at PROJECT_ROOT/cluster-cli , everything it operates on
# (the other repos, the relocated Helm charts, proxmox-tofu's kubeconfig) is
# a sibling of that, not something meant to be portable outside this layout.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KUBECONFIG_PATH = PROJECT_ROOT / "proxmox-tofu" / "_out" / "kubeconfig"
DEFAULT_CHARTS_DIR = PROJECT_ROOT / "charts"


@dataclass
class Config:
    runner_url: str
    api_token: str
    kubeconfig_path: Path


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Create it with:\n\n"
            '  runner_url = "https://ci.talos.lab"\n'
            '  api_token = "<from `tofu output -raw runner_api_token` in cluster-ci>"\n'
            f'  # kubeconfig_path = "..."  # optional, defaults to {DEFAULT_KUBECONFIG_PATH}\n'
        )
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    kubeconfig_path = Path(data["kubeconfig_path"]).expanduser() if "kubeconfig_path" in data else DEFAULT_KUBECONFIG_PATH
    return Config(runner_url=data["runner_url"], api_token=data["api_token"], kubeconfig_path=kubeconfig_path)
