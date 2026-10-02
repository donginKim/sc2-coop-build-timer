# SC2 협동전 빌드 오더 타이머 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SC2 협동전 게임 시간에 맞춰 빌드 단계를 반투명 오버레이와 한국어 음성으로 알려주는 Windows 트레이 앱을 만든다.

**Architecture:** SC2 클라이언트 로컬 API(`localhost:6119/game`)를 0.5초마다 폴링하는 `GameClock`이 게임 상태·시간을 내고, 순수 함수 `scheduler.tick`과 `Session`이 알릴 단계와 표시할 단계를 계산한다. Qt(PySide6) 계층(`overlay.py`, `app.py`)은 얇게 유지해 로직 전부를 Qt 없이 pytest로 검증한다. API가 안 되면 F9 수동 모드로 동작한다.

**Tech Stack:** Python 3.11+, uv, PySide6, PyYAML, pywin32(SAPI, Windows 전용), keyboard(전역 단축키, Windows 전용), PyInstaller, pytest

**Spec:** `docs/superpowers/specs/2026-10-02-sc2-coop-build-timer-design.md`

## Global Constraints

- Python `>=3.11`, 의존성 관리는 `uv` (`uv sync`, `uv run`).
- 게임 입력·자동 조작 코드 금지. 이 앱은 읽기(로컬 API)와 표시(오버레이·음성)만 한다.
- API 주소: `http://localhost:6119/game`, 폴링 간격 0.5초, 요청 timeout 0.3초, 시스템 프록시 무시.
- API 3회 연속 실패 시 수동 모드 전환.
- 앱 데이터 폴더: Windows `%APPDATA%/sc2coop_timer`, 그 외 `~/.sc2coop_timer`, 환경변수 `SC2COOP_HOME`이 있으면 그 경로.
- 빌드 탐색: 사용자 폴더 `<앱 데이터>/builds/*.yaml` → 내장 `sc2coop_timer/builds/*.yaml`. 같은 파일명은 사용자 폴더 우선.
- `lead_seconds` 기본값 3. 지난 단계 표시 유지 시간 2초. 오버레이 표시 단계 수 3.
- 단축키: F8 오버레이 표시/숨김, F9 수동 시작/정지, F10 같은 사령관 다음 빌드.
- 로그: `<앱 데이터>/log.txt`, 1MB 회전, 총 3개 파일.
- 내장 빌드 18개 모두 `verified: false` (타이밍은 검증 안 된 추정치).
- UI 문구·로그·에러 메시지는 한국어.

## Review Focus

1. 게임 중간에 앱을 켜거나 빌드를 바꿈 → 이미 지난 단계들이 한꺼번에 읽히지 않아야 한다 (Task 3 `test_stale_marked_silently`, Task 7 `test_fresh_session_mid_game_no_burst`).
2. 한 판이 끝나고 다음 판 시작(또는 리플레이 되감기) → 1:00 단계 등이 다시 알림되어야 한다 (Task 4 `test_new_game_after_menu_increments_id`, `test_time_drop_increments_id`, Task 7 `test_new_game_id_resets_announced`).
3. 사용자가 메모장으로 YAML을 고쳐 BOM이 붙거나 ANSI(cp949)로 저장 → BOM은 정상 로드, cp949는 "UTF-8로 저장" 안내 오류 (Task 2 `test_load_build_with_bom`, `test_load_build_cp949_gives_clear_error`).
4. 협동전 아군이 중간에 나감 → 그 플레이어 result가 확정돼도 내 게임은 계속 IN_GAME (Task 4 `test_ally_leaving_does_not_end_game`).
5. 게임 중 API 응답이 한두 번 실패 → 오버레이가 깜빡이거나 수동 모드로 넘어가지 않고 직전 값 유지 (Task 4 `test_transient_failure_keeps_last_reading`).

## File Structure

```
pyproject.toml, .python-version, .gitignore, run.py, build_exe.bat
sc2coop_timer/
  __init__.py
  __main__.py      python -m sc2coop_timer 진입
  main.py          인자 파싱, 로깅 설정, 조립 후 Qt 루프 실행
  probe.py         (표준 라이브러리만) API 응답 기록 도구 — Windows 실측용
  paths.py         앱 데이터·빌드 폴더 경로, 첫 실행 빌드 복사
  builds.py        YAML 로드·검증 → Build/Step
  scheduler.py     tick(): 알릴 단계·표시 단계 계산 (순수)
  clock.py         GameClock(API 폴링·상태·수동 모드), DemoClock, http_fetch
  tts.py           Speaker(큐+스레드), SapiBackend, ConsoleBackend
  overlay_model.py View/Row 생성, 표시 여부 (순수)
  session.py       Reading → Frame(View, visible, 읽을 문장) (순수, 상태 보유)
  config.py        config.yaml 로드·저장
  overlay.py       PySide6 오버레이 창
  hotkeys.py       Windows 전역 단축키 등록
  app.py           트레이 메뉴, 타이머 루프, 조립
  builds/*.yaml    내장 빌드 18개
tests/             pytest
docs/windows-setup.md
```

---

### Task 1: 프로젝트 골격 + API 프로브 도구

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `sc2coop_timer/__init__.py`, `sc2coop_timer/probe.py`
- Test: `tests/test_probe.py`

**Interfaces:**
- Consumes: 없음
- Produces: `sc2coop_timer.probe.summarize(game: dict | None, ui: dict | None) -> str`, `sc2coop_timer.probe.main(out: str = "probe.jsonl", interval: float = 1.0) -> None`. probe.py는 표준 라이브러리만 import (Windows에서 설치 없이 `python sc2coop_timer/probe.py` 실행 가능해야 함).

- [ ] **Step 1: 프로젝트 파일 작성**

`pyproject.toml`:

```toml
[project]
name = "sc2coop-timer"
version = "0.1.0"
description = "SC2 협동전 빌드 오더 타이머 (오버레이 + 음성)"
requires-python = ">=3.11"
dependencies = [
    "PySide6>=6.6",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
win = [
    "pywin32>=306; sys_platform == 'win32'",
    "keyboard>=0.13.5; sys_platform == 'win32'",
    "pyinstaller>=6.0",
]

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["sc2coop_timer*"]

[tool.setuptools.package-data]
sc2coop_timer = ["builds/*.yaml"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`.python-version`:

```
3.11
```

`.gitignore`:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
build/
dist/
*.spec
probe*.jsonl
*.egg-info/
```

`sc2coop_timer/__init__.py`:

```python
"""SC2 협동전 빌드 오더 타이머."""
```

- [ ] **Step 2: 의존성 설치**

Run: `uv sync`
Expected: `.venv` 생성, PySide6·PyYAML·pytest 설치 완료 (Python 3.11 자동 설치될 수 있음)

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/test_probe.py`:

```python
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
```

- [ ] **Step 4: 실패 확인**

Run: `uv run pytest tests/test_probe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sc2coop_timer.probe'`

- [ ] **Step 5: 구현**

`sc2coop_timer/probe.py`:

```python
"""SC2 로컬 API 응답을 1초마다 기록한다 (Windows 실측용).

표준 라이브러리만 사용한다. 설치 없이 실행:
    python sc2coop_timer/probe.py [출력파일]
협동전을 시작 → 1분 플레이 → 일시정지 10초 → 게임 종료 → 메뉴 복귀 후 Ctrl+C.
"""

import json
import sys
import time
import urllib.request

BASE = "http://localhost:6119"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path: str, timeout: float = 0.5) -> dict | None:
    try:
        with _opener.open(BASE + path, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def summarize(game: dict | None, ui: dict | None) -> str:
    if game is None:
        return "연결 안 됨"
    players = game.get("players") or []
    results = ",".join(f"{p.get('type', '?')}:{p.get('result', '?')}" for p in players)
    screens = len((ui or {}).get("activeScreens") or [])
    seconds = float(game.get("displayTime") or 0)
    return f"displayTime={seconds:.1f} players={len(players)} results=[{results}] screens={screens}"


def main(out: str = "probe.jsonl", interval: float = 1.0) -> None:
    print(f"{BASE} 기록 시작 → {out} (Ctrl+C로 종료)")
    with open(out, "a", encoding="utf-8") as f:
        while True:
            game, ui = get("/game"), get("/ui")
            f.write(json.dumps({"t": time.time(), "game": game, "ui": ui}, ensure_ascii=False) + "\n")
            f.flush()
            print(time.strftime("%H:%M:%S"), summarize(game, ui))
            time.sleep(interval)


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else "probe.jsonl")
    except KeyboardInterrupt:
        pass
```

- [ ] **Step 6: 통과 확인**

Run: `uv run pytest tests/test_probe.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .python-version .gitignore uv.lock sc2coop_timer/__init__.py sc2coop_timer/probe.py tests/test_probe.py
git commit -m "feat: scaffold project and add SC2 API probe tool"
```

---

### Task 2: 빌드 로더 + 경로

**Files:**
- Create: `sc2coop_timer/paths.py`, `sc2coop_timer/builds.py`
- Test: `tests/test_paths.py`, `tests/test_builds.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `paths.app_home() -> Path`, `paths.user_builds_dir() -> Path`, `paths.builtin_builds_dir() -> Path`, `paths.seed_user_builds(src: Path, dst: Path) -> int`
  - `builds.COMMANDERS: dict[str, str]` (id → 한국어 이름, 18개, 표시 순서 = 정의 순서)
  - `builds.BuildError(ValueError)`
  - `builds.Step(at: int, do: str, say: str, tag: str | None = None)` frozen dataclass
  - `builds.Build(key: str, commander: str, name: str, verified: bool, lead_seconds: float, steps: tuple[Step, ...])` frozen dataclass
  - `builds.parse_time(value) -> int`, `builds.parse_build(data, key: str) -> Build`, `builds.load_build(path: Path) -> Build`
  - `builds.load_all(dirs: list[Path]) -> tuple[dict[str, Build], list[str]]`
  - `builds.builds_by_commander(builds: dict[str, Build]) -> dict[str, list[Build]]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_paths.py`:

```python
from sc2coop_timer.paths import app_home, seed_user_builds, user_builds_dir


def test_app_home_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SC2COOP_HOME", str(tmp_path))
    assert app_home() == tmp_path
    assert user_builds_dir() == tmp_path / "builds"


def test_seed_copies_missing_only(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "a.yaml").write_text("A", encoding="utf-8")
    (src / "b.yaml").write_text("B", encoding="utf-8")
    (dst / "a.yaml").write_text("내가 고친 것", encoding="utf-8")

    assert seed_user_builds(src, dst) == 1
    assert (dst / "a.yaml").read_text(encoding="utf-8") == "내가 고친 것"
    assert (dst / "b.yaml").read_text(encoding="utf-8") == "B"


def test_seed_creates_dst(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.yaml").write_text("A", encoding="utf-8")
    assert seed_user_builds(src, tmp_path / "new" / "builds") == 1
```

`tests/test_builds.py`:

```python
import pytest

from sc2coop_timer.builds import (
    COMMANDERS,
    Build,
    BuildError,
    Step,
    builds_by_commander,
    load_all,
    load_build,
    parse_build,
    parse_time,
)

VALID_YAML = """\
commander: raynor
name: 테스트 빌드
steps:
  - at: "0:40"
    do: 보급고
    say: 보급고 올려
  - at: 4:00
    do: 첫 웨이브
    tag: wave
"""


def valid_data(**overrides):
    data = {
        "commander": "raynor",
        "name": "테스트",
        "steps": [{"at": "0:40", "do": "보급고"}],
    }
    data.update(overrides)
    return data


def test_commanders_has_18():
    assert len(COMMANDERS) == 18
    assert COMMANDERS["han_horner"] == "한&호너"


@pytest.mark.parametrize("text,expected", [("0:40", 40), ("4:00", 240), ("12:05", 725), (" 1:30 ", 90)])
def test_parse_time_string(text, expected):
    assert parse_time(text) == expected


def test_parse_time_int_is_seconds():
    # PyYAML은 따옴표 없는 4:00 을 60진수 정수 240으로 읽는다
    assert parse_time(240) == 240


@pytest.mark.parametrize("bad", ["4:6", "4:60", "abc", "", "1:2:3", -5, True, None, 1.5])
def test_parse_time_rejects(bad):
    with pytest.raises(BuildError):
        parse_time(bad)


def test_parse_build_defaults():
    b = parse_build(valid_data(), "t")
    assert b == Build(
        key="t",
        commander="raynor",
        name="테스트",
        verified=False,
        lead_seconds=3.0,
        steps=(Step(at=40, do="보급고", say="보급고", tag=None),),
    )


def test_parse_build_say_and_tag():
    data = valid_data(steps=[{"at": "1:00", "do": "웨이브", "say": "막아", "tag": "wave"}], lead_seconds=5, verified=True)
    b = parse_build(data, "t")
    assert b.steps[0] == Step(at=60, do="웨이브", say="막아", tag="wave")
    assert b.lead_seconds == 5.0
    assert b.verified is True


@pytest.mark.parametrize("field", ["commander", "name", "steps"])
def test_parse_build_missing_field(field):
    data = valid_data()
    del data[field]
    with pytest.raises(BuildError, match=f"필수 필드 누락: {field}"):
        parse_build(data, "t")


def test_parse_build_unknown_commander():
    with pytest.raises(BuildError, match="알 수 없는 사령관"):
        parse_build(valid_data(commander="jim"), "t")


def test_parse_build_not_mapping():
    with pytest.raises(BuildError, match="최상위"):
        parse_build(["a"], "t")


def test_parse_build_empty_steps():
    with pytest.raises(BuildError, match="steps가 비어"):
        parse_build(valid_data(steps=[]), "t")


def test_parse_build_step_missing_do():
    with pytest.raises(BuildError, match="2번째 단계"):
        parse_build(valid_data(steps=[{"at": "0:10", "do": "a"}, {"at": "0:20"}]), "t")


def test_parse_build_bad_time_names_step():
    with pytest.raises(BuildError, match="1번째 단계: 시간 형식 오류"):
        parse_build(valid_data(steps=[{"at": "4:6", "do": "a"}]), "t")


def test_parse_build_unsorted():
    steps = [{"at": "1:00", "do": "a"}, {"at": "0:30", "do": "b"}]
    with pytest.raises(BuildError, match="2번째 단계: 시간 순서"):
        parse_build(valid_data(steps=steps), "t")


def test_parse_build_same_time_allowed():
    steps = [{"at": "1:00", "do": "a"}, {"at": "1:00", "do": "b"}]
    assert len(parse_build(valid_data(steps=steps), "t").steps) == 2


def test_parse_build_bad_tag():
    with pytest.raises(BuildError, match="tag는 wave/objective"):
        parse_build(valid_data(steps=[{"at": "0:10", "do": "a", "tag": "boss"}]), "t")


@pytest.mark.parametrize("lead", [-1, "3", True])
def test_parse_build_bad_lead(lead):
    with pytest.raises(BuildError, match="lead_seconds"):
        parse_build(valid_data(lead_seconds=lead), "t")


def test_load_build_file(tmp_path):
    p = tmp_path / "raynor_test.yaml"
    p.write_text(VALID_YAML, encoding="utf-8")
    b = load_build(p)
    assert b.key == "raynor_test"
    assert [s.at for s in b.steps] == [40, 240]
    assert b.steps[0].say == "보급고 올려"


def test_load_build_with_bom(tmp_path):
    p = tmp_path / "bom.yaml"
    p.write_bytes(b"\xef\xbb\xbf" + VALID_YAML.encode("utf-8"))
    assert load_build(p).name == "테스트 빌드"


def test_load_build_cp949_gives_clear_error(tmp_path):
    p = tmp_path / "ansi.yaml"
    p.write_bytes(VALID_YAML.encode("cp949"))
    with pytest.raises(BuildError, match="ansi.yaml: UTF-8로 저장"):
        load_build(p)


def test_load_build_yaml_syntax_error_has_line(tmp_path):
    p = tmp_path / "broken.yaml"
    p.write_text("commander: raynor\nname: [닫히지 않음\nsteps: []\n", encoding="utf-8")
    with pytest.raises(BuildError, match=r"broken\.yaml:\d+: YAML 문법 오류"):
        load_build(p)


def test_load_build_validation_error_has_filename(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("commander: jim\nname: x\nsteps: [{at: '0:10', do: a}]\n", encoding="utf-8")
    with pytest.raises(BuildError, match="bad.yaml: 알 수 없는 사령관"):
        load_build(p)


def test_load_all_priority_and_errors(tmp_path):
    user, builtin = tmp_path / "user", tmp_path / "builtin"
    user.mkdir()
    builtin.mkdir()
    (builtin / "raynor.yaml").write_text(VALID_YAML, encoding="utf-8")
    (builtin / "kerrigan.yaml").write_text(VALID_YAML.replace("raynor", "kerrigan"), encoding="utf-8")
    (user / "raynor.yaml").write_text(VALID_YAML.replace("테스트 빌드", "내 빌드"), encoding="utf-8")
    (user / "broken.yaml").write_text("commander: [", encoding="utf-8")

    builds, errors = load_all([user, builtin, tmp_path / "없는폴더"])

    assert set(builds) == {"raynor", "kerrigan"}
    assert builds["raynor"].name == "내 빌드"
    assert len(errors) == 1 and errors[0].startswith("broken.yaml")


def test_builds_by_commander_order():
    def mk(key, commander):
        return Build(key, commander, key, False, 3.0, (Step(0, "a", "a"),))

    builds = {"z2": mk("z2", "zeratul"), "r1": mk("r1", "raynor"), "r2": mk("r2", "raynor")}
    grouped = builds_by_commander(builds)
    assert list(grouped) == ["raynor", "zeratul"]
    assert [b.key for b in grouped["raynor"]] == ["r1", "r2"]
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_paths.py tests/test_builds.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sc2coop_timer.paths'`

- [ ] **Step 3: 구현**

`sc2coop_timer/paths.py`:

```python
"""앱 데이터·빌드 폴더 경로."""

import os
import shutil
import sys
from pathlib import Path


def app_home() -> Path:
    override = os.environ.get("SC2COOP_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "sc2coop_timer"
    return Path.home() / ".sc2coop_timer"


def user_builds_dir() -> Path:
    return app_home() / "builds"


def builtin_builds_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "sc2coop_timer" / "builds"
    return Path(__file__).resolve().parent / "builds"


def seed_user_builds(src: Path, dst: Path) -> int:
    """src의 빌드 중 dst에 없는 파일만 복사한다. 복사한 개수를 반환."""
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(src.glob("*.yaml")):
        target = dst / path.name
        if not target.exists():
            shutil.copyfile(path, target)
            copied += 1
    return copied
```

`sc2coop_timer/builds.py`:

```python
"""빌드 YAML 로드·검증."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

COMMANDERS: dict[str, str] = {
    "raynor": "레이너",
    "kerrigan": "케리건",
    "artanis": "아르타니스",
    "swann": "스완",
    "zagara": "자가라",
    "vorazun": "보라준",
    "karax": "카락스",
    "abathur": "아바투르",
    "alarak": "알라라크",
    "nova": "노바",
    "stukov": "스투코프",
    "fenix": "피닉스",
    "dehaka": "데하카",
    "han_horner": "한&호너",
    "tychus": "타이커스",
    "zeratul": "제라툴",
    "stetmann": "스텟먼",
    "mengsk": "멩스크",
}
TAGS = {"wave", "objective"}
_TIME = re.compile(r"^(\d{1,2}):([0-5]\d)$")


class BuildError(ValueError):
    pass


@dataclass(frozen=True)
class Step:
    at: int
    do: str
    say: str
    tag: str | None = None


@dataclass(frozen=True)
class Build:
    key: str
    commander: str
    name: str
    verified: bool
    lead_seconds: float
    steps: tuple[Step, ...]


def parse_time(value) -> int:
    """'M:SS' 문자열 또는 초 단위 정수(PyYAML이 따옴표 없는 4:00을 240으로 읽음)를 초로 바꾼다."""
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise BuildError(f"시간 형식 오류 '{value}' (M:SS)")
        return value
    if not isinstance(value, str):
        raise BuildError(f"시간 형식 오류 '{value}' (M:SS)")
    m = _TIME.match(value.strip())
    if not m:
        raise BuildError(f"시간 형식 오류 '{value}' (M:SS)")
    return int(m.group(1)) * 60 + int(m.group(2))


def parse_build(data, key: str) -> Build:
    if not isinstance(data, dict):
        raise BuildError("최상위가 매핑(키: 값)이 아님")
    for field in ("commander", "name", "steps"):
        if field not in data:
            raise BuildError(f"필수 필드 누락: {field}")
    commander = data["commander"]
    if commander not in COMMANDERS:
        raise BuildError(f"알 수 없는 사령관: {commander}")
    raw_steps = data["steps"]
    if not isinstance(raw_steps, list) or not raw_steps:
        raise BuildError("steps가 비어 있음")

    steps: list[Step] = []
    for i, raw in enumerate(raw_steps, 1):
        where = f"{i}번째 단계"
        if not isinstance(raw, dict) or "at" not in raw or "do" not in raw:
            raise BuildError(f"{where}: at, do 필수")
        try:
            at = parse_time(raw["at"])
        except BuildError as e:
            raise BuildError(f"{where}: {e}") from None
        tag = raw.get("tag")
        if tag is not None and tag not in TAGS:
            raise BuildError(f"{where}: tag는 wave/objective만 가능 ('{tag}')")
        if steps and at < steps[-1].at:
            raise BuildError(f"{where}: 시간 순서가 앞 단계보다 빠름")
        do = str(raw["do"])
        steps.append(Step(at=at, do=do, say=str(raw.get("say") or do), tag=tag))

    lead = data.get("lead_seconds", 3)
    if isinstance(lead, bool) or not isinstance(lead, (int, float)) or lead < 0:
        raise BuildError("lead_seconds는 0 이상 숫자여야 함")

    return Build(
        key=key,
        commander=commander,
        name=str(data["name"]),
        verified=bool(data.get("verified", False)),
        lead_seconds=float(lead),
        steps=tuple(steps),
    )


def load_build(path: Path) -> Build:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise BuildError(f"{path.name}: UTF-8로 저장해야 함 (메모장 '다른 이름으로 저장' → 인코딩 UTF-8)") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = f":{mark.line + 1}" if mark is not None else ""
        raise BuildError(f"{path.name}{line}: YAML 문법 오류") from None
    try:
        return parse_build(data, path.stem)
    except BuildError as e:
        raise BuildError(f"{path.name}: {e}") from None


def load_all(dirs: list[Path]) -> tuple[dict[str, Build], list[str]]:
    """dirs 앞쪽 폴더가 우선. 같은 파일명은 처음 만난 것만 쓴다(오류여도 뒤 폴더로 대체하지 않음)."""
    builds: dict[str, Build] = {}
    errors: list[str] = []
    seen: set[str] = set()
    for d in dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.yaml")):
            if path.stem in seen:
                continue
            seen.add(path.stem)
            try:
                builds[path.stem] = load_build(path)
            except BuildError as e:
                errors.append(str(e))
    return builds, errors


def builds_by_commander(builds: dict[str, Build]) -> dict[str, list[Build]]:
    grouped: dict[str, list[Build]] = {}
    for commander in COMMANDERS:
        items = sorted((b for b in builds.values() if b.commander == commander), key=lambda b: b.key)
        if items:
            grouped[commander] = items
    return grouped
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_paths.py tests/test_builds.py -v`
Expected: 전부 PASS

- [ ] **Step 5: Commit**

```bash
git add sc2coop_timer/paths.py sc2coop_timer/builds.py tests/test_paths.py tests/test_builds.py
git commit -m "feat: add build YAML loader and app paths"
```

---

### Task 3: 스케줄러

**Files:**
- Create: `sc2coop_timer/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `builds.Step`
- Produces: `scheduler.LINGER = 2.0`, `scheduler.TickResult(announce: tuple[int, ...], display: tuple[int, ...], announced: frozenset[int])`, `scheduler.tick(game_seconds: float, steps: tuple[Step, ...], announced: frozenset[int], lead: float, show: int = 3) -> TickResult`

규칙 (스펙 3장 계약을 구체화):
- due: `step.at - lead <= t`
- 알림: due 이고 이전 `announced`에 없고 `t < step.at + LINGER` (이미 지난 단계는 조용히 처리 — 게임 중간 시작/빌드 변경 시 폭주 방지)
- 반환 `announced` = 현재 due 전체 (시간 역행 시 자동으로 줄어듦)
- 표시: `t < step.at + LINGER` 인 단계 중 앞에서 `show`개

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_scheduler.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sc2coop_timer.scheduler'`

- [ ] **Step 3: 구현**

`sc2coop_timer/scheduler.py`:

```python
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
) -> TickResult:
    t = game_seconds
    due = [i for i, s in enumerate(steps) if s.at - lead <= t]
    announce = tuple(i for i in due if i not in announced and t < steps[i].at + LINGER)
    display = tuple(i for i, s in enumerate(steps) if t < s.at + LINGER)[:show]
    return TickResult(announce=announce, display=display, announced=frozenset(due))
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: 전부 PASS

- [ ] **Step 5: Commit**

```bash
git add sc2coop_timer/scheduler.py tests/test_scheduler.py
git commit -m "feat: add build step scheduler"
```

---

### Task 4: 게임 시계

**Files:**
- Create: `sc2coop_timer/clock.py`
- Test: `tests/test_clock.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `clock.State` Enum: `MENU`, `LOADING`, `IN_GAME`, `ENDED`
  - `clock.Mode` Enum: `AUTO`, `MANUAL`
  - `clock.Reading(state: State, seconds: float, mode: Mode, game_id: int)` frozen dataclass
  - `clock.FetchError(Exception)`
  - `clock.API_URL = "http://localhost:6119/game"`
  - `clock.classify(game: dict) -> tuple[State, float]` (형식 이상 시 `ValueError`/`TypeError`/`AttributeError`)
  - `clock.http_fetch(url: str = API_URL, timeout: float = 0.3) -> dict` (실패 시 `FetchError`)
  - `clock.GameClock(fetch: Callable[[], dict], now: Callable[[], float] = time.monotonic, fail_limit: int = 3)` — `.poll() -> Reading`, `.toggle_manual() -> None`
  - `clock.DemoClock(speed: float = 1.0, now: Callable[[], float] = time.monotonic)` — 같은 `.poll()`, `.toggle_manual()` (재시작)

상태 판정 (⚠️ Task 1 프로브 실측 후 조정 가능):
- players 없음 → MENU
- "user" 타입 플레이어 전원(없으면 전체)의 result가 `Undecided`/없음이 아님 → ENDED
- displayTime ≤ 0 → LOADING, 그 외 IN_GAME

game_id 증가 규칙: LOADING에 새로 진입 / MENU·ENDED에서 바로 IN_GAME / IN_GAME 중 시간이 1초 넘게 줄어듦 / 수동 시작.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_clock.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_clock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sc2coop_timer.clock'`

- [ ] **Step 3: 구현**

`sc2coop_timer/clock.py`:

```python
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

    def poll(self) -> Reading:
        try:
            game = self._fetch()
        except FetchError:
            self._fails += 1
            if self._fails >= self._fail_limit and self._mode is Mode.AUTO:
                log.warning("SC2 API 연결 %d회 실패 — 수동 모드(F9)로 전환", self._fails)
                self._mode = Mode.MANUAL
            return self._remember(self._fallback())

        self._fails = 0
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
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_clock.py -v`
Expected: 전부 PASS

- [ ] **Step 5: Commit**

```bash
git add sc2coop_timer/clock.py tests/test_clock.py
git commit -m "feat: add game clock with SC2 API polling and manual fallback"
```

---

### Task 5: 음성 출력

**Files:**
- Create: `sc2coop_timer/tts.py`
- Test: `tests/test_tts.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `tts.Speaker(backend_factory: Callable[[], Backend], now: Callable[[], float] = time.monotonic, max_age: float = 5.0)` — `.say(text: str)`, `.close(timeout: float = 2.0)`, 속성 `.enabled: bool`, `.failed: bool`
  - Backend 프로토콜: `.speak(text: str) -> None` (동기, 말이 끝날 때까지 블록)
  - `tts.ConsoleBackend`, `tts.SapiBackend`, `tts.default_backend_factory() -> Backend`

`backend_factory`는 워커 스레드 안에서 호출된다 (SAPI COM 초기화가 같은 스레드여야 함). 큐에서 `max_age`초 넘게 기다린 문장은 버린다 (늦은 알림이 엉뚱한 때 나오는 것 방지).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tts.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_tts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sc2coop_timer.tts'`

- [ ] **Step 3: 구현**

`sc2coop_timer/tts.py`:

```python
"""음성 알림. 워커 스레드 하나가 큐를 순서대로 읽는다."""

import logging
import queue
import sys
import threading
import time
from typing import Callable, Protocol

log = logging.getLogger(__name__)


class Backend(Protocol):
    def speak(self, text: str) -> None: ...


class ConsoleBackend:
    def speak(self, text: str) -> None:
        print(f"[TTS] {text}", flush=True)


class SapiBackend:
    """Windows SAPI. 반드시 사용할 스레드 안에서 생성한다."""

    def __init__(self):
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        self._voice = win32com.client.Dispatch("SAPI.SpVoice")
        voices = self._voice.GetVoices()
        for i in range(voices.Count):
            desc = voices.Item(i).GetDescription()
            if "korean" in desc.lower() or "한국어" in desc:
                self._voice.Voice = voices.Item(i)
                break
        else:
            log.warning("한국어 음성을 찾지 못함 — 기본 음성 사용")

    def speak(self, text: str) -> None:
        self._voice.Speak(text)


def default_backend_factory() -> Backend:
    if sys.platform == "win32":
        return SapiBackend()
    return ConsoleBackend()


class Speaker:
    def __init__(
        self,
        backend_factory: Callable[[], Backend],
        now: Callable[[], float] = time.monotonic,
        max_age: float = 5.0,
    ):
        self.enabled = True
        self.failed = False
        self._factory = backend_factory
        self._now = now
        self._max_age = max_age
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="tts", daemon=True)
        self._thread.start()

    def say(self, text: str) -> None:
        if self.enabled:
            self._queue.put((self._now(), text))

    def close(self, timeout: float = 2.0) -> None:
        self._queue.put(None)
        self._thread.join(timeout)

    def _run(self) -> None:
        try:
            backend = self._factory()
        except Exception:
            log.exception("TTS 초기화 실패 — 음성 없이 동작")
            self.failed = True
            backend = None
        while True:
            item = self._queue.get()
            if item is None:
                return
            queued_at, text = item
            if backend is None or self._now() - queued_at > self._max_age:
                continue
            try:
                backend.speak(text)
            except Exception:
                log.exception("TTS 출력 실패: %s", text)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_tts.py -v`
Expected: 전부 PASS

- [ ] **Step 5: Commit**

```bash
git add sc2coop_timer/tts.py tests/test_tts.py
git commit -m "feat: add queued TTS speaker with SAPI backend"
```

---

### Task 6: 내장 빌드 18개

**Files:**
- Create: `sc2coop_timer/builds/<commander>.yaml` × 18
- Test: `tests/test_builtin_builds.py`

**Interfaces:**
- Consumes: `builds.load_all`, `builds.COMMANDERS`, `paths.builtin_builds_dir`
- Produces: 내장 빌드 파일 (파일명 = 사령관 id)

모든 타이밍은 일반적인 협동전 운영 흐름 기반 ⚠️추정치다. 첫 공격 웨이브 시각은 맵마다 다르므로 4:00 근처 대비 알림으로만 둔다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_builtin_builds.py`:

```python
from sc2coop_timer.builds import COMMANDERS, load_all
from sc2coop_timer.paths import builtin_builds_dir


def test_builtin_builds_all_valid_and_cover_every_commander():
    builds, errors = load_all([builtin_builds_dir()])
    assert errors == []
    assert set(builds) == set(COMMANDERS)
    assert {b.commander for b in builds.values()} == set(COMMANDERS)


def test_builtin_builds_marked_unverified():
    builds, _ = load_all([builtin_builds_dir()])
    assert all(b.verified is False for b in builds.values())
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_builtin_builds.py -v`
Expected: FAIL — `set(builds)`가 빈 집합

- [ ] **Step 3: 빌드 파일 작성**

`sc2coop_timer/builds/raynor.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: raynor
name: 레이너 기본 (해병·의무관 → 전차)
verified: false
steps:
  - at: "0:00"
    do: SCV 계속 생산
  - at: "0:18"
    do: 보급고
  - at: "0:40"
    do: 정제소 2개
  - at: "0:55"
    do: 병영
  - at: "1:30"
    do: 병영 반응로, 해병 생산 시작
    say: 해병 생산 시작
  - at: "2:10"
    do: 공학 연구소, 보병 무기 업그레이드
    say: 공학 연구소
  - at: "3:00"
    do: 확장 기지 정리 후 사령부
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "4:30"
    do: 군수공장, 공성 전차
    say: 군수공장
  - at: "6:00"
    do: 무기고, 차량 업그레이드
    say: 무기고
  - at: "7:30"
    do: 우주공항, 전투순양함 준비
    say: 우주공항
```

`sc2coop_timer/builds/kerrigan.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: kerrigan
name: 케리건 기본 (케리건 + 히드라·울트라)
verified: false
steps:
  - at: "0:00"
    do: 드론 계속 생산
  - at: "0:20"
    do: 대군주
  - at: "0:40"
    do: 산란못
  - at: "0:55"
    do: 추출장 2개
  - at: "1:30"
    do: 케리건과 저글링으로 주변 정리
    say: 케리건 출격
  - at: "2:15"
    do: 진화장, 업그레이드
    say: 진화장
  - at: "2:45"
    do: 번식지
  - at: "3:00"
    do: 확장 해처리
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "4:30"
    do: 히드라리스크 굴
    say: 히드라 굴
  - at: "7:00"
    do: 군락, 울트라리스크 동굴
    say: 군락
```

`sc2coop_timer/builds/artanis.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: artanis
name: 아르타니스 기본 (광전사·용기병 → 고급 유닛)
verified: false
steps:
  - at: "0:00"
    do: 탐사정 계속 생산
  - at: "0:18"
    do: 수정탑
  - at: "0:40"
    do: 융화소 2개
  - at: "0:55"
    do: 관문
  - at: "1:30"
    do: 인공제어소
  - at: "2:00"
    do: 관문 추가, 광전사·용기병 생산
    say: 관문 추가
  - at: "2:40"
    do: 황혼 의회, 돌진 업그레이드
    say: 황혼 의회
  - at: "3:00"
    do: 확장 연결체
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 로봇공학 시설
    say: 로봇공학 시설
  - at: "6:30"
    do: 우주관문 또는 고위 기사 테크
    say: 상위 테크
```

`sc2coop_timer/builds/swann.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: swann
name: 스완 기본 (골리앗·전차 + 레이저 드릴)
verified: false
steps:
  - at: "0:00"
    do: SCV 계속 생산
  - at: "0:18"
    do: 보급고
  - at: "0:35"
    do: 정제소 2개
  - at: "0:50"
    do: 군수공장
  - at: "1:10"
    do: 레이저 드릴 업그레이드
    say: 레이저 드릴
  - at: "1:40"
    do: 군수공장 추가, 골리앗 생산
    say: 골리앗 생산
  - at: "2:30"
    do: 무기고
  - at: "3:00"
    do: 확장 기지 정리 후 사령부
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 공성 전차 추가
    say: 전차 추가
  - at: "7:00"
    do: 우주공항, 과학선
    say: 우주공항
```

`sc2coop_timer/builds/zagara.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: zagara
name: 자가라 기본 (저글링·맹독충 물량)
verified: false
steps:
  - at: "0:00"
    do: 드론 계속 생산
  - at: "0:20"
    do: 대군주
  - at: "0:35"
    do: 산란못
  - at: "0:50"
    do: 추출장 1개
  - at: "1:10"
    do: 저글링 대량 생산
    say: 저글링 생산
  - at: "1:40"
    do: 맹독충 둥지
  - at: "2:20"
    do: 진화장, 근접 공격 업그레이드
    say: 진화장
  - at: "2:50"
    do: 추출장 추가, 번식지
    say: 번식지
  - at: "3:10"
    do: 확장 해처리
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "6:00"
    do: 상위 테크와 공중 유닛 준비
    say: 상위 테크
```

`sc2coop_timer/builds/vorazun.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: vorazun
name: 보라준 기본 (암흑 기사 → 공허 포격기)
verified: false
steps:
  - at: "0:00"
    do: 탐사정 계속 생산
  - at: "0:18"
    do: 수정탑
  - at: "0:40"
    do: 융화소 2개
  - at: "0:55"
    do: 관문
  - at: "1:30"
    do: 인공제어소
  - at: "2:00"
    do: 황혼 의회
  - at: "2:40"
    do: 암흑 성소, 암흑 기사 생산
    say: 암흑 성소
  - at: "3:00"
    do: 확장 연결체
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 우주관문 2개, 공허 포격기
    say: 우주관문
  - at: "7:00"
    do: 함대 신호소, 공중 업그레이드
    say: 함대 신호소
```

`sc2coop_timer/builds/karax.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: karax
name: 카락스 기본 (방어 건물 + 로봇)
verified: false
steps:
  - at: "0:00"
    do: 탐사정 계속 생산
  - at: "0:18"
    do: 수정탑
  - at: "0:40"
    do: 융화소 2개
  - at: "0:55"
    do: 관문
  - at: "1:20"
    do: 제련소, 광자포 배치
    say: 광자포
  - at: "1:50"
    do: 인공제어소
  - at: "2:30"
    do: 로봇공학 시설
  - at: "3:00"
    do: 확장 연결체, 입구 광자포
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 로봇공학 지원소, 거신
    say: 거신
  - at: "7:00"
    do: 우주관문, 함대 신호소
    say: 공중 테크
```

`sc2coop_timer/builds/abathur.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: abathur
name: 아바투르 기본 (바퀴·뮤탈 → 군단 숙주)
verified: false
steps:
  - at: "0:00"
    do: 드론 계속 생산
  - at: "0:20"
    do: 대군주
  - at: "0:40"
    do: 산란못
  - at: "0:55"
    do: 추출장 2개
  - at: "1:20"
    do: 진화 둥지
    say: 진화 둥지
  - at: "1:40"
    do: 바퀴 소굴, 바퀴 생산
    say: 바퀴 생산
  - at: "2:40"
    do: 번식지
  - at: "3:00"
    do: 확장 해처리
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 둥지탑, 뮤탈리스크
    say: 둥지탑
  - at: "7:30"
    do: 바이오매스 확인, 상위 유닛 진화
    say: 바이오매스 확인
```

`sc2coop_timer/builds/alarak.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: alarak
name: 알라라크 기본 (알라라크 + 승천자)
verified: false
steps:
  - at: "0:00"
    do: 탐사정 계속 생산
  - at: "0:18"
    do: 수정탑
  - at: "0:40"
    do: 융화소 2개
  - at: "0:55"
    do: 관문
  - at: "1:20"
    do: 알라라크로 주변 정리
    say: 알라라크 출격
  - at: "1:50"
    do: 인공제어소
  - at: "2:40"
    do: 황혼 의회 계열 테크
    say: 황혼 의회
  - at: "3:00"
    do: 확장 연결체
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:30"
    do: 승천자 생산 테크
    say: 승천자 테크
  - at: "7:30"
    do: 공중 유닛 테크
    say: 공중 테크
```

`sc2coop_timer/builds/nova.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: nova
name: 노바 기본 (노바 + 정예 보병·기갑)
verified: false
steps:
  - at: "0:00"
    do: SCV 계속 생산
  - at: "0:18"
    do: 보급고
  - at: "0:40"
    do: 정제소 2개
  - at: "0:55"
    do: 병영
  - at: "1:20"
    do: 노바로 주변 정리
    say: 노바 출격
  - at: "2:00"
    do: 정예 해병 생산
    say: 해병 생산
  - at: "2:40"
    do: 군수공장
  - at: "3:00"
    do: 확장 기지 정리 후 사령부
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 공학 연구소·무기고 업그레이드
    say: 업그레이드
  - at: "7:00"
    do: 우주공항
```

`sc2coop_timer/builds/stukov.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: stukov
name: 스투코프 기본 (감염된 벙커 + 해병)
verified: false
steps:
  - at: "0:00"
    do: SCV 계속 생산
  - at: "0:18"
    do: 보급고
  - at: "0:40"
    do: 정제소 2개
  - at: "0:55"
    do: 감염된 병영
    say: 병영
  - at: "1:30"
    do: 감염된 벙커 배치
    say: 벙커
  - at: "2:10"
    do: 공학 연구소, 업그레이드
    say: 공학 연구소
  - at: "3:00"
    do: 확장 기지 정리 후 사령부
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "4:40"
    do: 군수공장 계열 테크
    say: 군수공장
  - at: "7:00"
    do: 우주공항 계열 테크
    say: 우주공항
```

`sc2coop_timer/builds/fenix.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: fenix
name: 피닉스 기본 (피닉스 + 용사 유닛)
verified: false
steps:
  - at: "0:00"
    do: 탐사정 계속 생산
  - at: "0:18"
    do: 수정탑
  - at: "0:40"
    do: 융화소 2개
  - at: "0:55"
    do: 관문
  - at: "1:20"
    do: 피닉스로 주변 정리
    say: 피닉스 출격
  - at: "1:50"
    do: 인공제어소
  - at: "2:30"
    do: 관문 추가, 유닛 생산
    say: 관문 추가
  - at: "3:00"
    do: 확장 연결체
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 로봇공학 시설
  - at: "7:00"
    do: 우주관문
```

`sc2coop_timer/builds/dehaka.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: dehaka
name: 데하카 기본 (데하카 정수 수집 + 원시 저그)
verified: false
steps:
  - at: "0:00"
    do: 드론 계속 생산
  - at: "0:20"
    do: 대군주 역할 건물 확인 후 보급 확보
    say: 보급 확보
  - at: "0:40"
    do: 추출장 2개
  - at: "1:00"
    do: 데하카로 적 처치, 정수 수집
    say: 데하카 출격
  - at: "1:40"
    do: 원시 저그 생산 건물
    say: 생산 건물
  - at: "2:30"
    do: 업그레이드 건물
    say: 업그레이드
  - at: "3:00"
    do: 확장 부화장
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 상위 원시 저그 테크
    say: 상위 테크
  - at: "8:00"
    do: 무리 우두머리 소환 타이밍 확인
    say: 우두머리 확인
```

`sc2coop_timer/builds/han_horner.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: han_horner
name: 한&호너 기본 (미라 용병 + 호너 공중)
verified: false
steps:
  - at: "0:00"
    do: SCV 계속 생산
  - at: "0:18"
    do: 보급고
  - at: "0:40"
    do: 정제소 2개
  - at: "0:55"
    do: 미라의 병영
    say: 병영
  - at: "1:30"
    do: 용병 생산 시작
    say: 용병 생산
  - at: "2:30"
    do: 우주공항, 호너 공중 유닛
    say: 우주공항
  - at: "3:00"
    do: 확장 기지 정리 후 사령부
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 공학 연구소·무기고 업그레이드
    say: 업그레이드
  - at: "7:00"
    do: 공중 함대 확장
    say: 함대 확장
```

`sc2coop_timer/builds/tychus.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: tychus
name: 타이커스 기본 (무법자 영웅 고용)
verified: false
steps:
  - at: "0:00"
    do: SCV 계속 생산
  - at: "0:18"
    do: 보급고
  - at: "0:40"
    do: 정제소 2개
  - at: "1:00"
    do: 타이커스로 주변 정리
    say: 타이커스 출격
  - at: "1:40"
    do: 두 번째 무법자 고용
    say: 무법자 고용
  - at: "2:30"
    do: 장비 업그레이드
    say: 장비 업그레이드
  - at: "3:00"
    do: 확장 기지 정리 후 사령부
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 세 번째 무법자 고용
    say: 무법자 고용
  - at: "8:00"
    do: 네 번째 무법자 고용
    say: 무법자 고용
```

`sc2coop_timer/builds/zeratul.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: zeratul
name: 제라툴 기본 (제라툴 + 유물 수집)
verified: false
steps:
  - at: "0:00"
    do: 탐사정 계속 생산
  - at: "0:18"
    do: 수정탑
  - at: "0:40"
    do: 융화소 2개
  - at: "1:00"
    do: 제라툴로 주변 정리, 유물 조각 확인
    say: 유물 확인
  - at: "1:40"
    do: 생산 건물
    say: 생산 건물
  - at: "2:30"
    do: 업그레이드 건물
    say: 업그레이드
  - at: "3:00"
    do: 확장 연결체
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:30"
    do: 상위 유닛 테크
    say: 상위 테크
  - at: "8:00"
    do: 유물 조각 다시 확인
    say: 유물 확인
```

`sc2coop_timer/builds/stetmann.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: stetmann
name: 스텟먼 기본 (메카 저그 + 스텟텔라이트)
verified: false
steps:
  - at: "0:00"
    do: 드론 계속 생산
  - at: "0:20"
    do: 보급 확보
  - at: "0:40"
    do: 추출장 2개
  - at: "0:55"
    do: 메카 저글링 생산 건물
    say: 생산 건물
  - at: "1:30"
    do: 스텟텔라이트 배치
    say: 스텟텔라이트
  - at: "2:20"
    do: 업그레이드 건물
    say: 업그레이드
  - at: "3:00"
    do: 확장
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 메카 히드라 테크
    say: 히드라 테크
  - at: "7:00"
    do: 상위 메카 유닛 테크
    say: 상위 테크
```

`sc2coop_timer/builds/mengsk.yaml`:

```yaml
# ⚠️ 추정치 — 실제 플레이로 타이밍을 조정하세요
commander: mengsk
name: 멩스크 기본 (병력 + 권위 관리)
verified: false
steps:
  - at: "0:00"
    do: SCV 계속 생산
  - at: "0:18"
    do: 보급고
  - at: "0:40"
    do: 정제소 2개
  - at: "0:55"
    do: 병영
  - at: "1:30"
    do: 병력 생산 시작
    say: 병력 생산
  - at: "2:20"
    do: 공학 연구소, 업그레이드
    say: 공학 연구소
  - at: "3:00"
    do: 확장 기지 정리 후 사령부
    say: 확장 준비
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave
  - at: "5:00"
    do: 군수공장·우주공항 테크
    say: 상위 테크
  - at: "7:00"
    do: 권위 확인, 전투 지원 능력 준비
    say: 권위 확인
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_builtin_builds.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add sc2coop_timer/builds tests/test_builtin_builds.py
git commit -m "feat: add estimated default builds for all 18 commanders"
```

---

### Task 7: 화면 모델 + 세션

**Files:**
- Create: `sc2coop_timer/overlay_model.py`, `sc2coop_timer/session.py`
- Test: `tests/test_overlay_model.py`, `tests/test_session.py`

**Interfaces:**
- Consumes: `builds.Build`, `builds.Step`, `builds.COMMANDERS`, `clock.Reading`, `clock.State`, `clock.Mode`, `scheduler.tick`
- Produces:
  - `overlay_model.Row(time: str, text: str, style: str)` — style ∈ `"normal" | "due" | "wave" | "objective" | "done"`
  - `overlay_model.View(title: str, clock: str, rows: tuple[Row, ...], badge: str)`
  - `overlay_model.fmt(seconds: float) -> str` (`M:SS`)
  - `overlay_model.build_view(build: Build | None, display: tuple[int, ...], game_seconds: float, mode: Mode) -> View`
  - `overlay_model.overlay_visible(state: State, flip: bool) -> bool`
  - `session.Frame(view: View, visible: bool, say: tuple[str, ...])`
  - `session.Session(build: Build | None = None)` — `.build`, `.set_build(build: Build | None)`, `.toggle_visibility()`, `.update(reading: Reading) -> Frame`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_overlay_model.py`:

```python
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
```

`tests/test_session.py`:

```python
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
    assert s.update(R(State.IN_GAME, 1.0)).visible is False


def test_ended_does_not_speak():
    s = Session(B)
    assert s.update(R(State.ENDED, 37.5)).say == ()


def test_no_build_frame():
    f = Session(None).update(R(State.IN_GAME, 5.0))
    assert f.say == ()
    assert f.view.title.startswith("빌드 없음")
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_overlay_model.py tests/test_session.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sc2coop_timer.overlay_model'`

- [ ] **Step 3: 구현**

`sc2coop_timer/overlay_model.py`:

```python
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
```

`sc2coop_timer/session.py`:

```python
"""시계 읽기값 → 화면·음성 출력. 알린 단계와 F8 표시 상태를 보관한다."""

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

    def set_build(self, build: Build | None) -> None:
        self.build = build
        self._announced = frozenset()

    def toggle_visibility(self) -> None:
        self._flip = not self._flip

    def update(self, reading: Reading) -> Frame:
        if reading.game_id != self._game_id:
            self._game_id = reading.game_id
            self._announced = frozenset()

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
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_overlay_model.py tests/test_session.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 전체 테스트**

Run: `uv run pytest -q`
Expected: 전부 PASS

- [ ] **Step 6: Commit**

```bash
git add sc2coop_timer/overlay_model.py sc2coop_timer/session.py tests/test_overlay_model.py tests/test_session.py
git commit -m "feat: add overlay view model and session state"
```

---

### Task 8: 설정 + 오버레이 창 + 트레이 앱

**Files:**
- Create: `sc2coop_timer/config.py`, `sc2coop_timer/overlay.py`, `sc2coop_timer/hotkeys.py`, `sc2coop_timer/app.py`, `sc2coop_timer/main.py`, `sc2coop_timer/__main__.py`, `run.py`
- Test: `tests/test_config.py` (Qt 계층은 Step 6 수동 확인)

**Interfaces:**
- Consumes: Task 2–7 전부
- Produces:
  - `config.Config` dataclass (`x: int | None`, `y: int | None`, `opacity: float = 0.8`, `voice: bool = True`, `last_build: str | None`, `first_run_done: bool = False`)
  - `config.load_config(path: Path) -> Config`, `config.save_config(cfg: Config, path: Path) -> None`
  - `overlay.Overlay(opacity: float)` — `.render(view: View)`, `.place(x: int | None, y: int | None)`
  - `hotkeys.register(bindings: dict[str, Callable[[], None]]) -> bool`
  - `app.App(clock, speaker: Speaker, home: Path)` — `.start()`
  - `main.setup_logging(home: Path) -> None`, `main.main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_config.py`:

```python
from sc2coop_timer.config import Config, load_config, save_config


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "없음.yaml") == Config()


def test_roundtrip(tmp_path):
    p = tmp_path / "sub" / "config.yaml"
    cfg = Config(x=10, y=20, opacity=0.5, voice=False, last_build="raynor", first_run_done=True)
    save_config(cfg, p)
    assert load_config(p) == cfg


def test_broken_yaml_gives_defaults(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("x: [", encoding="utf-8")
    assert load_config(p) == Config()


def test_bad_types_fall_back_per_field(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("x: abc\ny: true\nopacity: high\nvoice: false\nunknown: 1\n", encoding="utf-8")
    assert load_config(p) == Config(voice=False)


def test_opacity_clamped(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("opacity: 5\n", encoding="utf-8")
    assert load_config(p).opacity == 1.0
    p.write_text("opacity: 0\n", encoding="utf-8")
    assert load_config(p).opacity == 0.2
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sc2coop_timer.config'`

- [ ] **Step 3: config 구현**

`sc2coop_timer/config.py`:

```python
"""config.yaml 로드·저장. 잘못된 값은 해당 항목만 기본값으로."""

import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


@dataclass
class Config:
    x: int | None = None
    y: int | None = None
    opacity: float = 0.8
    voice: bool = True
    last_build: str | None = None
    first_run_done: bool = False


_TYPES: dict[str, tuple[type, ...]] = {
    "x": (int, type(None)),
    "y": (int, type(None)),
    "opacity": (int, float),
    "voice": (bool,),
    "last_build": (str, type(None)),
    "first_run_done": (bool,),
}


def _valid(name: str, value) -> bool:
    allowed = _TYPES[name]
    if isinstance(value, bool) and bool not in allowed:
        return False
    return isinstance(value, allowed)


def load_config(path: Path) -> Config:
    cfg = Config()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return cfg
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        log.warning("설정 파일을 읽지 못해 기본값 사용: %s", path)
        return cfg
    if not isinstance(data, dict):
        return cfg
    for f in fields(Config):
        if f.name in data and _valid(f.name, data[f.name]):
            setattr(cfg, f.name, data[f.name])
    cfg.opacity = min(1.0, max(0.2, float(cfg.opacity)))
    return cfg


def save_config(cfg: Config, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(asdict(cfg), allow_unicode=True), encoding="utf-8")
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_config.py -v`
Expected: 전부 PASS

- [ ] **Step 5: Qt 계층 구현**

`sc2coop_timer/overlay.py`:

```python
"""반투명·항상 위·클릭 통과 오버레이 창."""

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .overlay_model import View

WIDTH = 280
MARGIN = 16
COLORS = {
    "normal": "#e6e6e6",
    "due": "#7CFC00",
    "wave": "#ff6b6b",
    "objective": "#ffd166",
    "done": "#8a8a8a",
}


class Overlay(QWidget):
    def __init__(self, opacity: float):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(opacity)
        self.setFixedWidth(WIDTH)

        self._label = QLabel(self)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            "QLabel { background: rgba(0, 0, 0, 170); color: #e6e6e6;"
            " padding: 8px; border-radius: 6px; font-size: 13px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def render(self, view: View) -> None:
        badge = f" <span style='color:#ffd166'>{escape(view.badge)}</span>" if view.badge else ""
        head = (
            "<table width='100%'><tr>"
            f"<td><b>{escape(view.title)}</b>{badge}</td>"
            f"<td align='right'>[{view.clock}]</td>"
            "</tr></table>"
        )
        rows = []
        for row in view.rows:
            color = COLORS.get(row.style, COLORS["normal"])
            marker = "▶" if row.style == "due" else "&nbsp;&nbsp;"
            weight = "bold" if row.style == "due" else "normal"
            rows.append(
                f"<tr style='color:{color}; font-weight:{weight}'>"
                f"<td>{marker} {row.time}</td><td>&nbsp;{escape(row.text)}</td></tr>"
            )
        self._label.setText(head + "<table>" + "".join(rows) + "</table>")
        self.adjustSize()

    def place(self, x: int | None, y: int | None) -> None:
        if x is None or y is None:
            geo = QGuiApplication.primaryScreen().availableGeometry()
            x = geo.right() - WIDTH - MARGIN
            y = geo.top() + MARGIN
        self.move(x, y)
```

`sc2coop_timer/hotkeys.py`:

```python
"""전역 단축키 (Windows 전용, keyboard 패키지)."""

import logging
import sys
from typing import Callable

log = logging.getLogger(__name__)


def register(bindings: dict[str, Callable[[], None]]) -> bool:
    if sys.platform != "win32":
        log.info("전역 단축키는 Windows에서만 동작 — 트레이 메뉴를 사용하세요")
        return False
    try:
        import keyboard
    except ImportError:
        log.warning("keyboard 패키지가 없어 단축키 비활성")
        return False
    try:
        for key, callback in bindings.items():
            keyboard.add_hotkey(key, callback)
    except Exception:
        log.exception("단축키 등록 실패")
        return False
    return True
```

`sc2coop_timer/app.py`:

```python
"""트레이 메뉴 + 폴링 루프 조립."""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QActionGroup, QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from .builds import COMMANDERS, Build, builds_by_commander, load_all
from .config import load_config, save_config
from .hotkeys import register
from .overlay import Overlay
from .paths import builtin_builds_dir, seed_user_builds, user_builds_dir
from .session import Session
from .tts import Speaker

log = logging.getLogger(__name__)

POLL_MS = 500
APP_TITLE = "SC2 협동전 빌드 타이머"


class _Bridge(QObject):
    """단축키 스레드 → Qt 메인 스레드 전달."""

    toggle_overlay = Signal()
    toggle_manual = Signal()
    next_build = Signal()


class App:
    def __init__(self, clock, speaker: Speaker, home: Path):
        self.clock = clock
        self.speaker = speaker
        self.config_path = home / "config.yaml"
        self.cfg = load_config(self.config_path)
        self.speaker.enabled = self.cfg.voice
        self.session = Session()
        self.builds: dict[str, Build] = {}
        self._build_actions = {}

        self.overlay = Overlay(self.cfg.opacity)
        self.overlay.place(self.cfg.x, self.cfg.y)

        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip(APP_TITLE)
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)

        self.bridge = _Bridge()
        self.bridge.toggle_overlay.connect(self._toggle_overlay)
        self.bridge.toggle_manual.connect(self._toggle_manual)
        self.bridge.next_build.connect(self._next_build)

        self.timer = QTimer()
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        first_run = not self.cfg.first_run_done
        if first_run:
            seed_user_builds(builtin_builds_dir(), user_builds_dir())
            self.cfg.first_run_done = True
            save_config(self.cfg, self.config_path)
        self.tray.show()
        self.reload_builds()
        if first_run:
            self.tray.showMessage(
                APP_TITLE,
                "SC2 설정 → 그래픽 → 디스플레이 모드를 '창 모드(전체 화면)'으로 바꿔야 오버레이가 보입니다.",
            )
        register({
            "f8": self.bridge.toggle_overlay.emit,
            "f9": self.bridge.toggle_manual.emit,
            "f10": self.bridge.next_build.emit,
        })
        self.timer.start()
        self._on_tick()

    def reload_builds(self) -> None:
        self.builds, errors = load_all([user_builds_dir(), builtin_builds_dir()])
        for e in errors:
            log.warning("빌드 오류: %s", e)
        if errors:
            self.tray.showMessage("빌드 파일 오류", "\n".join(errors[:5]), QSystemTrayIcon.MessageIcon.Warning)
        self._rebuild_menu()
        key = self.cfg.last_build if self.cfg.last_build in self.builds else next(iter(sorted(self.builds)), None)
        self._select(key)

    def _rebuild_menu(self) -> None:
        self.menu.clear()
        self._build_actions = {}
        group = QActionGroup(self.menu)
        group.setExclusive(True)
        for commander, items in builds_by_commander(self.builds).items():
            sub = self.menu.addMenu(COMMANDERS[commander])
            for build in items:
                action = sub.addAction(build.name)
                action.setCheckable(True)
                group.addAction(action)
                action.triggered.connect(lambda _checked=False, k=build.key: self._select(k))
                self._build_actions[build.key] = action
        self.menu.addSeparator()
        voice = self.menu.addAction("음성 알림")
        voice.setCheckable(True)
        voice.setChecked(self.cfg.voice)
        voice.toggled.connect(self._set_voice)
        self.menu.addAction("빌드 폴더 열기").triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_builds_dir())))
        )
        self.menu.addAction("빌드 다시 읽기").triggered.connect(self.reload_builds)
        self.menu.addSeparator()
        self.menu.addAction("종료").triggered.connect(QApplication.quit)

    def _select(self, key: str | None) -> None:
        self.session.set_build(self.builds.get(key) if key else None)
        for k, action in self._build_actions.items():
            action.setChecked(k == key)
        if self.cfg.last_build != key:
            self.cfg.last_build = key
            save_config(self.cfg, self.config_path)

    def _next_build(self) -> None:
        current = self.session.build
        if current is None:
            return
        same = builds_by_commander(self.builds).get(current.commander, [])
        keys = [b.key for b in same]
        if current.key in keys:
            self._select(keys[(keys.index(current.key) + 1) % len(keys)])
            self._on_tick()

    def _set_voice(self, on: bool) -> None:
        self.cfg.voice = on
        self.speaker.enabled = on
        save_config(self.cfg, self.config_path)

    def _toggle_manual(self) -> None:
        self.clock.toggle_manual()
        self._on_tick()

    def _toggle_overlay(self) -> None:
        self.session.toggle_visibility()
        self._on_tick()

    def _on_tick(self) -> None:
        try:
            frame = self.session.update(self.clock.poll())
        except Exception:
            log.exception("tick 처리 실패")
            return
        for text in frame.say:
            self.speaker.say(text)
        self.overlay.render(frame.view)
        self.overlay.setVisible(frame.visible)
```

`sc2coop_timer/main.py`:

```python
"""진입점: 인자 파싱, 로깅, 조립."""

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .app import App
from .clock import DemoClock, GameClock, http_fetch
from .paths import app_home
from .tts import Speaker, default_backend_factory


def setup_logging(home: Path) -> None:
    handler = RotatingFileHandler(home / "log.txt", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sc2coop_timer", description="SC2 협동전 빌드 오더 타이머")
    parser.add_argument("--demo", type=float, metavar="SPEED", help="SC2 없이 가짜 게임 시계로 실행 (배속)")
    args = parser.parse_args(argv)

    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    setup_logging(home)

    qapp = QApplication(sys.argv[:1])
    qapp.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logging.warning("시스템 트레이를 사용할 수 없음")

    clock = DemoClock(speed=args.demo) if args.demo else GameClock(http_fetch)
    speaker = Speaker(default_backend_factory)
    app = App(clock, speaker, home)
    app.start()
    code = qapp.exec()
    speaker.close()
    return code
```

`sc2coop_timer/__main__.py`:

```python
from sc2coop_timer.main import main

raise SystemExit(main())
```

`run.py` (PyInstaller 진입점):

```python
from sc2coop_timer.main import main

raise SystemExit(main())
```

- [ ] **Step 6: Mac 데모 실행으로 수동 확인**

Run: `SC2COOP_HOME=$PWD/.demo_home uv run python -m sc2coop_timer --demo 10`
Expected (약 20초 관찰 후 Ctrl+C):
- 화면 우측 상단에 오버레이가 뜨고 시계가 10배속으로 흐름
- 터미널에 `[TTS] 일꾼 생산` 같은 줄이 단계 시각 3초 전에 출력됨
- 메뉴바 트레이 아이콘 → 사령관별 빌드 선택 시 오버레이 제목이 바뀜
- `.demo_home/builds/`에 내장 빌드 18개가 복사됨, `.demo_home/log.txt` 생성

확인 후 정리: `rm -rf .demo_home`

- [ ] **Step 7: 전체 테스트**

Run: `uv run pytest -q`
Expected: 전부 PASS

- [ ] **Step 8: Commit**

```bash
git add sc2coop_timer/config.py sc2coop_timer/overlay.py sc2coop_timer/hotkeys.py sc2coop_timer/app.py sc2coop_timer/main.py sc2coop_timer/__main__.py run.py tests/test_config.py
git commit -m "feat: add overlay window, tray app and entry point"
```

---

### Task 9: Windows 패키징 + 실측 가이드

**Files:**
- Create: `build_exe.bat`, `docs/windows-setup.md`

**Interfaces:**
- Consumes: `run.py`, `sc2coop_timer/builds/`
- Produces: `dist\sc2coop_timer.exe` (Windows에서 사용자가 빌드)

- [ ] **Step 1: 빌드 스크립트 작성**

`build_exe.bat`:

```bat
@echo off
rem Windows에서 실행: 단일 exe 빌드 → dist\sc2coop_timer.exe
uv sync --extra win || exit /b 1
uv run pyinstaller --noconfirm --noconsole --onefile --name sc2coop_timer ^
  --add-data "sc2coop_timer\builds;sc2coop_timer\builds" ^
  --hidden-import win32com.client --hidden-import pythoncom ^
  run.py
```

- [ ] **Step 2: Windows 가이드 작성**

`docs/windows-setup.md`:

````markdown
# Windows 설정·실측 가이드

## 1. 준비

1. uv 설치 (PowerShell):
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. 이 저장소 폴더를 Windows PC로 복사 (USB·클라우드 드라이브 등).
3. 폴더에서:
   ```powershell
   uv sync --extra win
   ```

## 2. API 실측 (먼저 할 것)

SC2 실행 → 협동전 시작 직전에:

```powershell
uv run python -m sc2coop_timer.probe
```

1분 플레이 → Esc로 일시정지 10초 → 게임 종료(승리/항복) → 메뉴 복귀 → Ctrl+C.
생성된 `probe.jsonl`을 개발 쪽에 전달하면 상태 판정 규칙을 실측값으로 확정한다.

## 3. 실행

```powershell
uv run python -m sc2coop_timer
```

- SC2 설정 → 그래픽 → 디스플레이 모드: **창 모드(전체 화면)**
- 트레이 아이콘 우클릭 → 사령관 → 빌드 선택
- F8 오버레이 표시/숨김, F9 수동 시작/정지, F10 다음 빌드
- 빌드 수정: 트레이 → 빌드 폴더 열기 → YAML 편집(UTF-8 저장) → 빌드 다시 읽기

## 4. exe 빌드

```powershell
.\build_exe.bat
```

결과: `dist\sc2coop_timer.exe`. 이 파일 하나만 있으면 실행된다.

## 5. 실측 체크리스트

- [ ] 협동전 중 `probe` 출력에 `displayTime`이 증가한다
- [ ] 일시정지 동안 `displayTime`이 멈춘다
- [ ] 창 모드(전체 화면)에서 오버레이가 게임 위에 보이고, 클릭이 게임으로 통과한다
- [ ] 한국어 음성으로 단계가 읽힌다 (없으면 설정 → 시간 및 언어 → 음성에서 한국어 음성 추가)
- [ ] 게임 중 F8/F9/F10이 동작한다 (안 되면 앱을 관리자 권한으로 실행해 볼 것)
- [ ] exe 실행 시 내장 빌드 18개가 트레이 메뉴에 보인다
````

- [ ] **Step 3: 전체 테스트**

Run: `uv run pytest -q`
Expected: 전부 PASS

- [ ] **Step 4: Commit**

```bash
git add build_exe.bat docs/windows-setup.md
git commit -m "docs: add Windows packaging script and field test guide"
```
