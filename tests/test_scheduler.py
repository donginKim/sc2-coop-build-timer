from sc2coop_timer.builds import Step
from sc2coop_timer.scheduler import LINGER, tick

S = (
    Step(0, "a", "a"),
    Step(40, "b", "b"),
    Step(60, "c", "c"),
    Step(60, "d", "d"),
    Step(120, "e", "e"),
)
NONE = frozenset()


def test_linger_constant():
    assert LINGER == 2.0


def test_first_step_announced_at_game_start():
    assert tick(0.5, S, NONE, 3).announce == (0,)


def test_lead_boundary():
    assert tick(36.9, S, frozenset({0}), 3).announce == ()
    assert tick(37.0, S, frozenset({0}), 3).announce == (1,)


def test_lead_zero():
    assert tick(39.9, S, frozenset({0}), 0).announce == ()
    assert tick(40.0, S, frozenset({0}), 0).announce == (1,)


def test_not_repeated():
    r1 = tick(37.0, S, frozenset({0}), 3)
    r2 = tick(37.5, S, r1.announced, 3)
    assert r2.announce == ()
    assert r2.announced == frozenset({0, 1})


def test_multiple_steps_same_tick():
    assert tick(57.0, S, frozenset({0, 1}), 3).announce == (2, 3)


def test_just_passed_within_linger_still_announced():
    # 폴링이 늦어 at을 1초 넘겨도 LINGER 안이면 알린다
    assert tick(61.0, S, frozenset({0, 1}), 3).announce == (2, 3)


def test_stale_marked_silently():
    r = tick(100.0, S, NONE, 3)
    assert r.announce == ()
    assert r.announced == frozenset({0, 1, 2, 3})


def test_rewind_unannounces():
    r = tick(10.0, S, frozenset({0, 1, 2, 3}), 3)
    assert r.announced == frozenset({0})
    assert tick(37.0, S, r.announced, 3).announce == (1,)


def test_display_next_three_with_linger():
    assert tick(41.0, S, frozenset({0, 1}), 3).display == (1, 2, 3)
    assert tick(42.0, S, frozenset({0, 1}), 3).display == (2, 3, 4)


def test_display_show_param():
    assert tick(0.0, S, NONE, 3, show=2).display == (0, 1)


def test_display_after_last_step_empty():
    assert tick(200.0, S, NONE, 3).display == ()


def test_empty_steps():
    r = tick(5.0, (), NONE, 3)
    assert (r.announce, r.display, r.announced) == ((), (), frozenset())


def test_skipped_steps_not_displayed_or_announced():
    r = tick(37.0, S, frozenset({0}), 3, skipped=frozenset({1}))
    assert r.announce == ()
    assert r.display == (2, 3, 4)
