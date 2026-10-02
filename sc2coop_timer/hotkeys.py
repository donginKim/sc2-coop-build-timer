"""전역 단축키 (Windows 전용, keyboard 패키지)."""

import logging
import sys
from typing import Callable

log = logging.getLogger(__name__)


def register(bindings: dict[str, Callable[[], None]]) -> bool:
    if sys.platform != "win32":
        log.info("전역 단축키는 Windows에서만 동작 — 트레이 메뉴를 사용하세요")
        return False
    try:
        import keyboard
    except ImportError:
        log.warning("keyboard 패키지가 없어 단축키 비활성")
        return False
    try:
        for key, callback in bindings.items():
            keyboard.add_hotkey(key, callback)
    except Exception:
        log.exception("단축키 등록 실패")
        return False
    return True
