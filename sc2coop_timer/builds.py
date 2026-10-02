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
    if not isinstance(commander, str) or commander not in COMMANDERS:
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
        if tag is not None and (not isinstance(tag, str) or tag not in TAGS):
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
    except OSError as e:
        raise BuildError(f"{path.name}: 파일을 읽을 수 없음 ({e.strerror})") from None
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
