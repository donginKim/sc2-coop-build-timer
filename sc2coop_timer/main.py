"""진입점: 인자 파싱, 로깅, 조립."""

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .app import App
from .clock import DemoClock, GameClock, http_fetch
from .paths import app_home
from .tts import Speaker, default_backend_factory


def setup_logging(home: Path) -> None:
    handler = RotatingFileHandler(home / "log.txt", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sc2coop_timer", description="SC2 협동전 빌드 오더 타이머")
    parser.add_argument("--demo", type=float, metavar="SPEED", help="SC2 없이 가짜 게임 시계로 실행 (배속)")
    args = parser.parse_args(argv)

    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    setup_logging(home)

    qapp = QApplication(sys.argv[:1])
    qapp.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logging.warning("시스템 트레이를 사용할 수 없음")

    clock = DemoClock(speed=args.demo) if args.demo else GameClock(http_fetch)
    speaker = Speaker(default_backend_factory)
    app = App(clock, speaker, home)
    app.start()
    code = qapp.exec()
    speaker.close()
    return code
