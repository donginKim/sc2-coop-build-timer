import pytest

from sc2coop_timer.clock import (
    DemoClock,
    FetchError,
    GameClock,
    Mode,
    Reading,
    State,
    classify,
)


def game(t, results=("Undecided", "Undecided"), types=("user", "computer")):
    return {
        "displayTime": t,
        "players": [{"type": ty, "result": r} for ty, r in zip(types, results)],
    }


MENU_GAME = {"displayTime": 0, "players": []}


class FakeApi:
    """응답 목록을 순서대로 돌려준다. 예외 인스턴스면 raise."""

    def __init__(self, responses):
        self.responses = list(responses)

    def __call__(self):
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeNow:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


# --- classify ---

def test_classify_menu():
    assert classify(MENU_GAME) == (State.MENU, 0.0)
    assert classify({}) == (State.MENU, 0.0)


def test_classify_loading():
    assert classify(game(0)) == (State.LOADING, 0.0)


def test_classify_in_game():
    assert classify(game(75.5)) == (State.IN_GAME, 75.5)


def test_classify_ended():
    assert classify(game(900, results=("Victory", "Defeat"))) == (State.ENDED, 900.0)


def test_ally_leaving_does_not_end_game():
    g = game(300, results=("Undecided", "Defeat", "Undecided"), types=("user", "user", "computer"))
    assert classify(g) == (State.IN_GAME, 300.0)


def test_classify_ended_without_types():
    g = {"displayTime": 10, "players": [{"result": "Victory"}]}
    assert classify(g)[0] is State.ENDED


@pytest.mark.parametrize("bad", [{"players": "x"}, {"players": ["x"]}, {"players": [{}], "displayTime": "abc"}])
def test_classify_malformed_raises(bad):
    with pytest.raises((ValueError, TypeError, AttributeError)):
        classify(bad)


# --- GameClock 자동 모드 ---

def test_loading_then_in_game_same_id():
    clock = GameClock(FakeApi([MENU_GAME, game(0), game(1.0), game(2.0)]))
    readings = [clock.poll() for _ in range(4)]
    assert [r.state for r in readings] == [State.MENU, State.LOADING, State.IN_GAME, State.IN_GAME]
    assert readings[1].game_id == readings[2].game_id == readings[3].game_id == 1
    assert all(r.mode is Mode.AUTO for r in readings)


def test_new_game_after_menu_increments_id():
    clock = GameClock(FakeApi([game(5), game(900, results=("Victory", "Victory")), MENU_GAME, game(0), game(1)]))
    ids = [clock.poll().game_id for _ in range(5)]
    assert ids == [1, 1, 1, 2, 2]


def test_menu_to_in_game_without_loading_increments_id():
    clock = GameClock(FakeApi([MENU_GAME, game(3)]))
    clock.poll()
    assert clock.poll().game_id == 1


def test_time_drop_increments_id():
    clock = GameClock(FakeApi([game(100), game(101), game(2)]))
    ids = [clock.poll().game_id for _ in range(3)]
    assert ids == [1, 1, 2]


def test_transient_failure_keeps_last_reading():
    clock = GameClock(FakeApi([game(10), FetchError("x"), FetchError("x"), game(11)]))
    first = clock.poll()
    assert clock.poll() == first
    assert clock.poll() == first
    r = clock.poll()
    assert (r.state, r.seconds, r.mode) == (State.IN_GAME, 11.0, Mode.AUTO)


def test_malformed_response_keeps_last_reading():
    clock = GameClock(FakeApi([game(10), {"players": "x"}]))
    first = clock.poll()
    assert clock.poll() == first


def test_failures_before_any_success_report_menu():
    clock = GameClock(FakeApi([FetchError("x")]))
    assert clock.poll() == Reading(State.MENU, 0.0, Mode.AUTO, 0)


# --- 수동 모드 ---

def test_three_failures_switch_to_manual():
    clock = GameClock(FakeApi([FetchError("x")] * 3))
    clock.poll()
    clock.poll()
    r = clock.poll()
    assert r.mode is Mode.MANUAL
    assert r.state is State.MENU


def test_manual_timer_runs_from_toggle():
    now = FakeNow(100.0)
    clock = GameClock(FakeApi([FetchError("x")] * 5), now=now)
    for _ in range(3):
        clock.poll()
    clock.toggle_manual()
    now.t = 130.0
    r = clock.poll()
    assert (r.state, r.seconds, r.mode, r.game_id) == (State.IN_GAME, 30.0, Mode.MANUAL, 1)
    clock.toggle_manual()
    assert clock.poll().state is State.MENU


def test_manual_running_ignores_api_recovery():
    now = FakeNow(0.0)
    clock = GameClock(FakeApi([FetchError("x")] * 3 + [game(500)]), now=now)
    for _ in range(3):
        clock.poll()
    clock.toggle_manual()
    now.t = 5.0
    r = clock.poll()
    assert (r.mode, r.seconds) == (Mode.MANUAL, 5.0)


def test_manual_stopped_returns_to_auto_on_recovery():
    clock = GameClock(FakeApi([FetchError("x")] * 3 + [game(7)]))
    for _ in range(3):
        clock.poll()
    r = clock.poll()
    assert (r.mode, r.state, r.seconds) == (Mode.AUTO, State.IN_GAME, 7.0)


def test_toggle_manual_while_auto_forces_manual():
    now = FakeNow(0.0)
    clock = GameClock(FakeApi([game(50), game(51)]), now=now)
    clock.poll()
    clock.toggle_manual()
    now.t = 2.0
    r = clock.poll()
    assert (r.mode, r.seconds, r.game_id) == (Mode.MANUAL, 2.0, 2)


# --- DemoClock ---

def test_demo_clock_speed_and_restart():
    now = FakeNow(10.0)
    demo = DemoClock(speed=10.0, now=now)
    now.t = 12.0
    assert demo.poll() == Reading(State.IN_GAME, 20.0, Mode.AUTO, 1)
    demo.toggle_manual()
    assert demo.poll().seconds == 0.0
    assert demo.poll().game_id == 2


def test_outage_mid_game_keeps_extrapolating():
    now = FakeNow(0.0)
    clock = GameClock(FakeApi([game(100)] + [FetchError("x")] * 3 + [game(104)]), now=now)
    first = clock.poll()
    for _ in range(3):
        now.t += 1.0
        r = clock.poll()
    assert (r.state, r.seconds, r.mode, r.game_id) == (State.IN_GAME, 103.0, Mode.MANUAL, first.game_id)
    now.t += 1.0
    r = clock.poll()
    assert (r.state, r.seconds, r.mode, r.game_id) == (State.IN_GAME, 104.0, Mode.AUTO, first.game_id)
