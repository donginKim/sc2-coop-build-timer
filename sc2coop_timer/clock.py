"""SC2 로컬 API로 게임 상태·시간을 읽는 시계. API가 안 되면 수동 모드."""

import json
import logging
import time
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Callable

log = logging.getLogger(__name__)

API_URL = "http://localhost:6119/game"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class State(Enum):
    MENU = "menu"
    LOADING = "loading"
    IN_GAME = "in_game"
    ENDED = "ended"


class Mode(Enum):
    AUTO = "auto"
    MANUAL = "manual"


@dataclass(frozen=True)
class Reading:
    state: State
    seconds: float
    mode: Mode
    game_id: int


class FetchError(Exception):
    pass


def http_fetch(url: str = API_URL, timeout: float = 0.3) -> dict:
    try:
        with _opener.open(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError) as e:
        raise FetchError(str(e)) from e
    if not isinstance(data, dict):
        raise FetchError("응답이 JSON 객체가 아님")
    return data


def classify(game: dict) -> tuple[State, float]:
    players = game.get("players")
    if players is None:
        players = []
    if not isinstance(players, list):
        raise ValueError("players 형식 이상")
    t = float(game.get("displayTime") or 0.0)
    if not players:
        return State.MENU, 0.0
    users = [p for p in players if p.get("type") == "user"] or players
    if all(p.get("result") not in (None, "Undecided") for p in users):
        return State.ENDED, t
    if t <= 0:
        return State.LOADING, 0.0
    return State.IN_GAME, t


class GameClock:
    def __init__(
        self,
        fetch: Callable[[], dict],
        now: Callable[[], float] = time.monotonic,
        fail_limit: int = 3,
    ):
        self._fetch = fetch
        self._now = now
        self._fail_limit = fail_limit
        self._fails = 0
        self._mode = Mode.AUTO
        self._manual_start: float | None = None
        self._outage = False  # API 장애로 자동 전환된 수동 모드 (복구 시 자동 모드로 복귀)
        self._last_ok_at = 0.0
        self._game_id = 0
        self._last_state = State.MENU
        self._last_t = 0.0
        self._last: Reading | None = None

    def toggle_manual(self) -> None:
        if self._manual_start is None:
            self._mode = Mode.MANUAL
            self._manual_start = self._now()
            self._game_id += 1
        else:
            self._manual_start = None
        self._outage = False

    def poll(self) -> Reading:
        try:
            game = self._fetch()
        except FetchError:
            self._fails += 1
            if self._fails >= self._fail_limit and self._mode is Mode.AUTO:
                log.warning("SC2 API 연결 %d회 실패 — 수동 모드(Ctrl+Alt+F9)로 전환", self._fails)
                self._mode = Mode.MANUAL
                if self._last_state is State.IN_GAME:
                    # 게임 중 장애: 마지막 게임 시간에서 이어서 센다
                    self._manual_start = self._last_ok_at - self._last_t
                    self._outage = True
            return self._remember(self._fallback())

        self._fails = 0
        if self._outage:
            self._manual_start = None
            self._outage = False
        if self._mode is Mode.MANUAL and self._manual_start is None:
            log.info("SC2 API 연결 복구 — 자동 모드")
            self._mode = Mode.AUTO
        if self._mode is Mode.MANUAL:
            return self._remember(self._manual_reading())

        try:
            state, t = classify(game)
        except (ValueError, TypeError, AttributeError):
            log.warning("SC2 API 응답 형식 이상, 이번 tick 무시: %r", game)
            return self._remember(self._fallback())

        self._track_game(state, t)
        return self._remember(Reading(state, t, Mode.AUTO, self._game_id))

    def _fallback(self) -> Reading:
        if self._mode is Mode.MANUAL:
            return self._manual_reading()
        if self._last is not None:
            return self._last
        return Reading(State.MENU, 0.0, Mode.AUTO, self._game_id)

    def _manual_reading(self) -> Reading:
        if self._manual_start is None:
            return Reading(State.MENU, 0.0, Mode.MANUAL, self._game_id)
        return Reading(State.IN_GAME, self._now() - self._manual_start, Mode.MANUAL, self._game_id)

    def _track_game(self, state: State, t: float) -> None:
        last = self._last_state
        if state is State.LOADING:
            new = last is not State.LOADING
        elif state is State.IN_GAME:
            if last is State.LOADING:
                new = False
            elif last is State.IN_GAME:
                new = t < self._last_t - 1.0
            else:
                new = True
        else:
            new = False
        if new:
            self._game_id += 1
        self._last_state, self._last_t = state, t
        self._last_ok_at = self._now()

    def _remember(self, reading: Reading) -> Reading:
        self._last = reading
        return reading


class DemoClock:
    """SC2 없이 오버레이를 확인하기 위한 가짜 시계."""

    def __init__(self, speed: float = 1.0, now: Callable[[], float] = time.monotonic):
        self._speed = speed
        self._now = now
        self._start = now()
        self._game_id = 1

    def poll(self) -> Reading:
        return Reading(State.IN_GAME, (self._now() - self._start) * self._speed, Mode.AUTO, self._game_id)

    def toggle_manual(self) -> None:
        self._start = self._now()
        self._game_id += 1
