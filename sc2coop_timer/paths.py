"""앱 데이터·빌드 폴더 경로."""

import os
import shutil
import sys
from pathlib import Path


def app_home() -> Path:
    override = os.environ.get("SC2COOP_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "sc2coop_timer"
    return Path.home() / ".sc2coop_timer"


def user_builds_dir() -> Path:
    return app_home() / "builds"


def builtin_builds_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "sc2coop_timer" / "builds"
    return Path(__file__).resolve().parent / "builds"


def seed_user_builds(src: Path, dst: Path) -> int:
    """src의 빌드 중 dst에 없는 파일만 복사한다. 복사한 개수를 반환."""
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(src.glob("*.yaml")):
        target = dst / path.name
        if not target.exists():
            shutil.copyfile(path, target)
            copied += 1
    return copied
