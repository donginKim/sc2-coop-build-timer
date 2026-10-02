"""시계 읽기값 → 화면·음성 출력. 알린 단계와 Ctrl+Alt+F8 표시 상태를 보관한다."""

from dataclasses import dataclass

from .builds import Build
from .clock import Reading, State
from .overlay_model import View, build_view, overlay_visible
from .scheduler import tick


@dataclass(frozen=True)
class Frame:
    view: View
    visible: bool
    say: tuple[str, ...]


class Session:
    def __init__(self, build: Build | None = None):
        self.build = build
        self._announced: frozenset[int] = frozenset()
        self._game_id: int | None = None
        self._flip = False
        self._auto_shown: bool | None = None

    def set_build(self, build: Build | None) -> None:
        self.build = build
        self._announced = frozenset()

    def toggle_visibility(self) -> None:
        self._flip = not self._flip

    def update(self, reading: Reading) -> Frame:
        if reading.game_id != self._game_id:
            self._game_id = reading.game_id
            self._announced = frozenset()
        auto_shown = overlay_visible(reading.state, False)
        if auto_shown != self._auto_shown:
            self._auto_shown = auto_shown
            self._flip = False  # Ctrl+Alt+F8 수동 전환은 메뉴 ↔ 게임이 바뀌면 해제

        display: tuple[int, ...] = ()
        say: tuple[str, ...] = ()
        if self.build is not None:
            result = tick(reading.seconds, self.build.steps, self._announced, self.build.lead_seconds)
            display = result.display
            if reading.state is State.IN_GAME:
                self._announced = result.announced
                say = tuple(self.build.steps[i].say for i in result.announce)

        view = build_view(self.build, display, reading.seconds, reading.mode)
        return Frame(view=view, visible=overlay_visible(reading.state, self._flip), say=say)
