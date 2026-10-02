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
