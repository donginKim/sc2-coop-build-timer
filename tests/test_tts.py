import threading

from sc2coop_timer.tts import ConsoleBackend, Speaker


class FakeBackend:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


def test_speaks_in_order():
    backend = FakeBackend()
    s = Speaker(lambda: backend)
    s.say("a")
    s.say("b")
    s.close()
    assert backend.spoken == ["a", "b"]
    assert s.failed is False


def test_disabled_drops():
    backend = FakeBackend()
    s = Speaker(lambda: backend)
    s.enabled = False
    s.say("a")
    s.close()
    assert backend.spoken == []


def test_factory_failure_sets_failed_without_crash():
    def boom():
        raise RuntimeError("음성 없음")

    s = Speaker(boom)
    s.say("a")
    s.close()
    assert s.failed is True


def test_speak_exception_does_not_stop_worker():
    class Flaky(FakeBackend):
        def speak(self, text):
            if text == "bad":
                raise RuntimeError("x")
            super().speak(text)

    backend = Flaky()
    s = Speaker(lambda: backend)
    s.say("bad")
    s.say("good")
    s.close()
    assert backend.spoken == ["good"]


def test_stale_messages_dropped():
    clock = [0.0]
    gate = threading.Event()
    backend = FakeBackend()

    def factory():
        gate.wait(2)
        return backend

    s = Speaker(factory, now=lambda: clock[0], max_age=5.0)
    s.say("old")
    clock[0] = 10.0
    s.say("new")
    gate.set()
    s.close()
    assert backend.spoken == ["new"]


def test_console_backend_prints(capsys):
    ConsoleBackend().speak("보급고")
    assert "[TTS] 보급고" in capsys.readouterr().out
