"""음성 알림. 워커 스레드 하나가 큐를 순서대로 읽는다."""

import logging
import queue
import sys
import threading
import time
from typing import Callable, Protocol

log = logging.getLogger(__name__)


class Backend(Protocol):
    def speak(self, text: str) -> None: ...


class ConsoleBackend:
    def speak(self, text: str) -> None:
        print(f"[TTS] {text}", flush=True)


class SapiBackend:
    """Windows SAPI. 반드시 사용할 스레드 안에서 생성한다."""

    def __init__(self):
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        self._voice = win32com.client.Dispatch("SAPI.SpVoice")
        voices = self._voice.GetVoices()
        for i in range(voices.Count):
            desc = voices.Item(i).GetDescription()
            if "korean" in desc.lower() or "한국어" in desc:
                self._voice.Voice = voices.Item(i)
                break
        else:
            log.warning("한국어 음성을 찾지 못함 — 기본 음성 사용")

    def speak(self, text: str) -> None:
        self._voice.Speak(text)


def default_backend_factory() -> Backend:
    if sys.platform == "win32":
        return SapiBackend()
    return ConsoleBackend()


class Speaker:
    def __init__(
        self,
        backend_factory: Callable[[], Backend],
        now: Callable[[], float] = time.monotonic,
        max_age: float = 5.0,
    ):
        self.enabled = True
        self.failed = False
        self._factory = backend_factory
        self._now = now
        self._max_age = max_age
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="tts", daemon=True)
        self._thread.start()

    def say(self, text: str) -> None:
        if self.enabled:
            self._queue.put((self._now(), text))

    def close(self, timeout: float = 2.0) -> None:
        self._queue.put(None)
        self._thread.join(timeout)

    def _run(self) -> None:
        try:
            backend = self._factory()
        except Exception:
            log.exception("TTS 초기화 실패 — 음성 없이 동작")
            self.failed = True
            backend = None
        while True:
            item = self._queue.get()
            if item is None:
                return
            queued_at, text = item
            if backend is None or self._now() - queued_at > self._max_age:
                continue
            try:
                backend.speak(text)
            except Exception:
                log.exception("TTS 출력 실패: %s", text)
