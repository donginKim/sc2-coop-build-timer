from sc2coop_timer.probe import summarize


def test_summarize_not_connected():
    assert summarize(None, None) == "연결 안 됨"


def test_summarize_in_game():
    game = {
        "displayTime": 75.25,
        "players": [
            {"type": "user", "result": "Undecided"},
            {"type": "computer", "result": "Undecided"},
        ],
    }
    ui = {"activeScreens": []}
    assert summarize(game, ui) == (
        "displayTime=75.2 players=2 results=[user:Undecided,computer:Undecided] screens=0"
    )


def test_summarize_missing_fields():
    assert summarize({}, None) == "displayTime=0.0 players=0 results=[] screens=0"
