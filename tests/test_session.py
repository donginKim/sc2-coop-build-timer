from sc2coop_timer.builds import Build, Step
from sc2coop_timer.clock import Mode, Reading, State
from sc2coop_timer.session import Session

B = Build(
    key="t",
    commander="raynor",
    name="테스트",
    verified=False,
    lead_seconds=3.0,
    steps=(Step(0, "일꾼", "일꾼 생산"), Step(40, "보급고", "보급고 올려"), Step(60, "병영", "병영")),
)


def R(state, t, game_id=1, mode=Mode.AUTO):
    return Reading(state, t, mode, game_id)


def test_loading_shows_but_does_not_speak():
    s = Session(B)
    f = s.update(R(State.LOADING, 0.0))
    assert f.say == ()
    assert f.visible is True
    assert [r.text for r in f.view.rows] == ["일꾼", "보급고", "병영"]


def test_in_game_speaks_say_text_once():
    s = Session(B)
    s.update(R(State.LOADING, 0.0))
    assert s.update(R(State.IN_GAME, 0.5)).say == ("일꾼 생산",)
    assert s.update(R(State.IN_GAME, 1.0)).say == ()
    assert s.update(R(State.IN_GAME, 37.0)).say == ("보급고 올려",)


def test_new_game_id_resets_announced():
    s = Session(B)
    s.update(R(State.IN_GAME, 0.5, game_id=1))
    assert s.update(R(State.IN_GAME, 0.5, game_id=2)).say == ("일꾼 생산",)


def test_fresh_session_mid_game_no_burst():
    s = Session(B)
    assert s.update(R(State.IN_GAME, 100.0)).say == ()


def test_set_build_mid_game_no_burst():
    s = Session(None)
    s.update(R(State.IN_GAME, 50.0))
    s.set_build(B)
    assert s.update(R(State.IN_GAME, 50.5)).say == ()
    assert s.update(R(State.IN_GAME, 57.0)).say == ("병영",)


def test_menu_hidden_and_toggle():
    s = Session(B)
    assert s.update(R(State.MENU, 0.0)).visible is False
    s.toggle_visibility()
    assert s.update(R(State.MENU, 0.0)).visible is True


def test_toggle_resets_when_game_starts():
    s = Session(B)
    s.update(R(State.MENU, 0.0))
    s.toggle_visibility()
    assert s.update(R(State.IN_GAME, 1.0)).visible is True


def test_hidden_mid_game_stays_hidden_in_menu():
    s = Session(B)
    s.update(R(State.IN_GAME, 1.0))
    s.toggle_visibility()
    assert s.update(R(State.IN_GAME, 2.0)).visible is False
    assert s.update(R(State.ENDED, 900.0)).visible is False


def test_ended_does_not_speak():
    s = Session(B)
    assert s.update(R(State.ENDED, 37.5)).say == ()


def test_no_build_frame():
    f = Session(None).update(R(State.IN_GAME, 5.0))
    assert f.say == ()
    assert f.view.title.startswith("빌드 없음")


def test_skip_next_hides_and_silences_next_step():
    s = Session(B)
    s.update(R(State.IN_GAME, 1.0))
    s.skip_next()
    f = s.update(R(State.IN_GAME, 2.0))
    assert [r.text for r in f.view.rows] == ["병영"]
    assert s.update(R(State.IN_GAME, 37.0)).say == ()


def test_skip_next_twice_skips_two_steps():
    s = Session(B)
    s.update(R(State.IN_GAME, 1.0))
    s.skip_next()
    s.skip_next()
    assert s.update(R(State.IN_GAME, 2.0)).view.rows == ()


def test_skips_reset_on_new_game_and_build_change():
    s = Session(B)
    s.update(R(State.IN_GAME, 1.0, game_id=1))
    s.skip_next()
    assert s.update(R(State.IN_GAME, 37.0, game_id=2)).say == ("보급고 올려",)
    s.skip_next()
    s.set_build(B)
    assert [r.text for r in s.update(R(State.IN_GAME, 38.0, game_id=2)).view.rows] == ["보급고", "병영"]


def test_skip_next_without_build_is_noop():
    s = Session(None)
    s.update(R(State.IN_GAME, 1.0))
    s.skip_next()
