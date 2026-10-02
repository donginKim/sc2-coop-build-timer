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
