"""config.yaml 로드·저장. 잘못된 값은 해당 항목만 기본값으로."""

import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


@dataclass
class Config:
    x: int | None = None
    y: int | None = None
    opacity: float = 0.8
    voice: bool = True
    last_build: str | None = None
    first_run_done: bool = False


_TYPES: dict[str, tuple[type, ...]] = {
    "x": (int, type(None)),
    "y": (int, type(None)),
    "opacity": (int, float),
    "voice": (bool,),
    "last_build": (str, type(None)),
    "first_run_done": (bool,),
}


def _valid(name: str, value) -> bool:
    allowed = _TYPES[name]
    if isinstance(value, bool) and bool not in allowed:
        return False
    return isinstance(value, allowed)


def load_config(path: Path) -> Config:
    cfg = Config()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return cfg
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        log.warning("설정 파일을 읽지 못해 기본값 사용: %s", path)
        return cfg
    if not isinstance(data, dict):
        return cfg
    for f in fields(Config):
        if f.name in data and _valid(f.name, data[f.name]):
            setattr(cfg, f.name, data[f.name])
    cfg.opacity = min(1.0, max(0.2, float(cfg.opacity)))
    return cfg


def save_config(cfg: Config, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(asdict(cfg), allow_unicode=True), encoding="utf-8")
