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
