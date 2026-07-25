"""User configuration: seed artists, genre keywords, scan window.

Config lives at ~/.config/riff-radar/config.json by default and can be
overridden with --config. Everything is plain JSON so it stays trivially
editable by hand or by an agent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "riff-radar" / "config.json"

DEFAULT_KEYWORDS = [
    "metalcore", "post-hardcore", "deathcore", "metal", "hardcore",
    "alt-rock", "prog", "djent", "emo", "screamo",
]

DEFAULT_SEED_ARTISTS = [
    "Sleep Token",
    "Spiritbox",
    "Bad Omens",
    "Architects",
    "Bring Me The Horizon",
]


@dataclass
class Config:
    seed_artists: list[str] = field(default_factory=lambda: list(DEFAULT_SEED_ARTISTS))
    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    # How far back a release can be and still count as "new".
    window_days: int = 14
    # How many related artists to pull per seed artist.
    related_per_seed: int = 10
    # Cap on total artists scanned per run (keeps API calls bounded).
    max_artists_per_scan: int = 60
    data_dir: str = "~/.local/share/riff-radar"

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).expanduser()


def load(path: Path | None = None) -> Config:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return Config()
    raw = json.loads(path.read_text())
    known = {f for f in Config.__dataclass_fields__}
    return Config(**{k: v for k, v in raw.items() if k in known})


def save(cfg: Config, path: Path | None = None) -> Path:
    path = path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2) + "\n")
    return path
