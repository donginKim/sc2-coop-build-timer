"""게임 시간 → 알릴 단계·표시할 단계 계산 (순수 함수)."""

from dataclasses import dataclass

from .builds import Step

LINGER = 2.0  # 지난 단계를 표시하고 늦은 알림을 허용하는 시간(초)


@dataclass(frozen=True)
class TickResult:
    announce: tuple[int, ...]
    display: tuple[int, ...]
    announced: frozenset[int]


def tick(
    game_seconds: float,
    steps: tuple[Step, ...],
    announced: frozenset[int],
    lead: float,
    show: int = 3,
    skipped: frozenset[int] = frozenset(),
) -> TickResult:
    t = game_seconds
    due = [i for i, s in enumerate(steps) if s.at - lead <= t]
    announce = tuple(i for i in due if i not in announced and i not in skipped and t < steps[i].at + LINGER)
    display = tuple(i for i, s in enumerate(steps) if i not in skipped and t < s.at + LINGER)[:show]
    return TickResult(announce=announce, display=display, announced=frozenset(due))
