import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ci-cli" / "config.toml"


@dataclass
class Config:
    runner_url: str
    api_token: str


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Create it with:\n\n"
            '  runner_url = "https://ci.talos.lab"\n'
            '  api_token = "<from `tofu output -raw runner_api_token` in cluster-ci>"\n'
        )
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return Config(runner_url=data["runner_url"], api_token=data["api_token"])
