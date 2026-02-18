from pathlib import Path
import imkerutils.paths as paths


def test_ensure_dirs_creates_expected_dirs(tmp_path, monkeypatch):
    # Rebind module-level paths to a temp “project root” for the test.
    fake_root = tmp_path

    monkeypatch.setattr(paths, "PROJECT_ROOT", fake_root)
    monkeypatch.setattr(paths, "GENERATED_ROOT", fake_root / "imkerutils" / "_generated")
    monkeypatch.setattr(paths, "OUTPUT_ROOT", fake_root / "outputs")

    monkeypatch.setattr(paths, "GENERATED_TILES", paths.GENERATED_ROOT / "tiles")
    monkeypatch.setattr(paths, "GENERATED_CACHE", paths.GENERATED_ROOT / "cache")
    monkeypatch.setattr(paths, "OUTPUT_IMAGES", paths.OUTPUT_ROOT / "images")
    monkeypatch.setattr(paths, "OUTPUT_TILES", paths.OUTPUT_ROOT / "tiles")

    paths.ensure_dirs()

    assert paths.GENERATED_ROOT.is_dir()
    assert paths.GENERATED_TILES.is_dir()
    assert paths.GENERATED_CACHE.is_dir()
    assert paths.OUTPUT_ROOT.is_dir()
    assert paths.OUTPUT_IMAGES.is_dir()
    assert paths.OUTPUT_TILES.is_dir()
