"""트레이 메뉴 + 폴링 루프 조립."""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QActionGroup, QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from .builds import COMMANDERS, Build, builds_by_commander, load_all
from .config import load_config, save_config
from .hotkeys import register
from .overlay import Overlay
from .paths import builtin_builds_dir, seed_user_builds, user_builds_dir
from .session import Session
from .tts import Speaker

log = logging.getLogger(__name__)

POLL_MS = 500
APP_TITLE = "SC2 협동전 빌드 타이머"


class _Bridge(QObject):
    """단축키 스레드 → Qt 메인 스레드 전달."""

    toggle_overlay = Signal()
    toggle_manual = Signal()
    next_build = Signal()


class App:
    def __init__(self, clock, speaker: Speaker, home: Path):
        self.clock = clock
        self.speaker = speaker
        self.config_path = home / "config.yaml"
        self.cfg = load_config(self.config_path)
        self.speaker.enabled = self.cfg.voice
        self.session = Session()
        self.builds: dict[str, Build] = {}
        self._build_actions = {}

        self.overlay = Overlay(self.cfg.opacity)
        self.overlay.place(self.cfg.x, self.cfg.y)

        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip(APP_TITLE)
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)

        self.bridge = _Bridge()
        self.bridge.toggle_overlay.connect(self._toggle_overlay)
        self.bridge.toggle_manual.connect(self._toggle_manual)
        self.bridge.next_build.connect(self._next_build)

        self.timer = QTimer()
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        first_run = not self.cfg.first_run_done
        if first_run:
            seed_user_builds(builtin_builds_dir(), user_builds_dir())
            self.cfg.first_run_done = True
            save_config(self.cfg, self.config_path)
        self.tray.show()
        self.reload_builds()
        if first_run:
            self.tray.showMessage(
                APP_TITLE,
                "SC2 설정 → 그래픽 → 디스플레이 모드를 '창 모드(전체 화면)'으로 바꿔야 오버레이가 보입니다.",
            )
        register({
            "f8": self.bridge.toggle_overlay.emit,
            "f9": self.bridge.toggle_manual.emit,
            "f10": self.bridge.next_build.emit,
        })
        self.timer.start()
        self._on_tick()

    def reload_builds(self) -> None:
        self.builds, errors = load_all([user_builds_dir(), builtin_builds_dir()])
        for e in errors:
            log.warning("빌드 오류: %s", e)
        if errors:
            self.tray.showMessage("빌드 파일 오류", "\n".join(errors[:5]), QSystemTrayIcon.MessageIcon.Warning)
        self._rebuild_menu()
        key = self.cfg.last_build if self.cfg.last_build in self.builds else next(iter(sorted(self.builds)), None)
        self._select(key)

    def _rebuild_menu(self) -> None:
        self.menu.clear()
        self._build_actions = {}
        group = QActionGroup(self.menu)
        group.setExclusive(True)
        for commander, items in builds_by_commander(self.builds).items():
            sub = self.menu.addMenu(COMMANDERS[commander])
            for build in items:
                action = sub.addAction(build.name)
                action.setCheckable(True)
                group.addAction(action)
                action.triggered.connect(lambda _checked=False, k=build.key: self._select(k))
                self._build_actions[build.key] = action
        self.menu.addSeparator()
        voice = self.menu.addAction("음성 알림")
        voice.setCheckable(True)
        voice.setChecked(self.cfg.voice)
        voice.toggled.connect(self._set_voice)
        self.menu.addAction("빌드 폴더 열기").triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_builds_dir())))
        )
        self.menu.addAction("빌드 다시 읽기").triggered.connect(self.reload_builds)
        self.menu.addSeparator()
        self.menu.addAction("종료").triggered.connect(QApplication.quit)

    def _select(self, key: str | None) -> None:
        self.session.set_build(self.builds.get(key) if key else None)
        for k, action in self._build_actions.items():
            action.setChecked(k == key)
        if self.cfg.last_build != key:
            self.cfg.last_build = key
            save_config(self.cfg, self.config_path)

    def _next_build(self) -> None:
        current = self.session.build
        if current is None:
            return
        same = builds_by_commander(self.builds).get(current.commander, [])
        keys = [b.key for b in same]
        if current.key in keys:
            self._select(keys[(keys.index(current.key) + 1) % len(keys)])
            self._on_tick()

    def _set_voice(self, on: bool) -> None:
        self.cfg.voice = on
        self.speaker.enabled = on
        save_config(self.cfg, self.config_path)

    def _toggle_manual(self) -> None:
        self.clock.toggle_manual()
        self._on_tick()

    def _toggle_overlay(self) -> None:
        self.session.toggle_visibility()
        self._on_tick()

    def _on_tick(self) -> None:
        try:
            frame = self.session.update(self.clock.poll())
        except Exception:
            log.exception("tick 처리 실패")
            return
        for text in frame.say:
            self.speaker.say(text)
        self.overlay.render(frame.view)
        self.overlay.setVisible(frame.visible)
