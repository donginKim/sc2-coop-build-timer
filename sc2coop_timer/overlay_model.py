"""오버레이에 그릴 내용 계산 (Qt 없음)."""

from dataclasses import dataclass

from .builds import COMMANDERS, Build
from .clock import Mode, State


@dataclass(frozen=True)
class Row:
    time: str
    text: str
    style: str  # normal | due | wave | objective | done


@dataclass(frozen=True)
class View:
    title: str
    clock: str
    rows: tuple[Row, ...]
    badge: str


def fmt(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


def build_view(build: Build | None, display: tuple[int, ...], game_seconds: float, mode: Mode) -> View:
    badges = []
    if mode is Mode.MANUAL:
        badges.append("수동 모드")
    if build is None:
        return View(title="빌드 없음 — 빌드 폴더 확인", clock=fmt(game_seconds), rows=(), badge=" ".join(badges))
    if not build.verified:
        badges.append("⚠️추정치")

    rows = []
    for i in display:
        step = build.steps[i]
        if step.at <= game_seconds:
            style = "done"
        elif step.at - build.lead_seconds <= game_seconds:
            style = "due"
        else:
            style = step.tag or "normal"
        rows.append(Row(fmt(step.at), step.do, style))

    return View(
        title=f"{COMMANDERS[build.commander]} · {build.name}",
        clock=fmt(game_seconds),
        rows=tuple(rows),
        badge=" ".join(badges),
    )


def overlay_visible(state: State, flip: bool) -> bool:
    auto = state in (State.LOADING, State.IN_GAME)
    return auto != flip
