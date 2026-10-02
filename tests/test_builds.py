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
