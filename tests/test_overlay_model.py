import pytest

from sc2coop_timer.builds import Build, Step
from sc2coop_timer.clock import Mode, State
from sc2coop_timer.overlay_model import Row, View, build_view, fmt, overlay_visible

B = Build(
    key="t",
    commander="raynor",
    name="테스트",
    verified=False,
    lead_seconds=3.0,
    steps=(Step(40, "보급고", "보급고"), Step(60, "웨이브", "웨이브", "wave"), Step(90, "목표", "목표", "objective"), Step(120, "기타", "기타")),
)


@pytest.mark.parametrize("sec,text", [(0, "0:00"), (75.9, "1:15"), (-1, "0:00"), (754, "12:34")])
def test_fmt(sec, text):
    assert fmt(sec) == text


def test_build_view_styles():
    v = build_view(B, (0, 1, 2), 41.0, Mode.AUTO)
    assert v == View(
        title="레이너 · 테스트",
        clock="0:41",
        rows=(Row("0:40", "보급고", "done"), Row("1:00", "웨이브", "wave"), Row("1:30", "목표", "objective")),
        badge="⚠️추정치",
    )


def test_build_view_due_overrides_tag():
    v = build_view(B, (1,), 57.0, Mode.AUTO)
    assert v.rows == (Row("1:00", "웨이브", "due"),)


def test_build_view_normal_and_verified():
    verified = Build("v", "raynor", "검증", True, 3.0, B.steps)
    v = build_view(verified, (3,), 0.0, Mode.AUTO)
    assert v.rows == (Row("2:00", "기타", "normal"),)
    assert v.badge == ""


def test_build_view_manual_badge():
    assert build_view(B, (), 0.0, Mode.MANUAL).badge == "수동 모드 ⚠️추정치"


def test_build_view_no_build():
    v = build_view(None, (), 5.0, Mode.AUTO)
    assert v == View(title="빌드 없음 — 빌드 폴더 확인", clock="0:05", rows=(), badge="")


@pytest.mark.parametrize(
    "state,flip,expected",
    [
        (State.MENU, False, False),
        (State.ENDED, False, False),
        (State.LOADING, False, True),
        (State.IN_GAME, False, True),
        (State.IN_GAME, True, False),
        (State.MENU, True, True),
    ],
)
def test_overlay_visible(state, flip, expected):
    assert overlay_visible(state, flip) is expected
