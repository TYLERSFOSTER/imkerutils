from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from imkerutils.exquisite.pipeline.session import ExquisiteSession
from imkerutils.exquisite.geometry.tile_mode import TILE_PX


def _write_initial_canvas(path: Path) -> None:
    img = Image.new("RGB", (TILE_PX, TILE_PX))
    img.save(path, format="PNG")


@pytest.mark.parametrize("mode", ["x_ltr", "x_rtl", "y_ttb", "y_btt"])
def test_create_session_writes_expected_artifacts(tmp_path: Path, mode: str) -> None:
    initial = tmp_path / "initial.png"
    _write_initial_canvas(initial)

    artifact_root = tmp_path / "_generated" / "exquisite"

    sess = ExquisiteSession.create(
        initial_canvas_path=initial,
        mode=mode,  # type: ignore[arg-type]
        artifact_root=artifact_root,
    )

    root = Path(sess.state.session_root)
    assert root.exists()

    assert (root / "canvas_latest.png").exists()
    assert (root / "session_state.json").exists()
    assert (root / "steps" / "0000").exists()
    assert (root / "steps" / "0000" / "canvas_initial.png").exists()
    assert (root / "steps" / "0000" / "committed.ok").exists()


@pytest.mark.parametrize("mode", ["x_ltr", "x_rtl", "y_ttb", "y_btt"])
def test_one_disk_step_commits_and_grows(tmp_path: Path, mode: str) -> None:
    initial = tmp_path / "initial.png"
    _write_initial_canvas(initial)

    artifact_root = tmp_path / "_generated" / "exquisite"
    sess = ExquisiteSession.create(initial_canvas_path=initial, mode=mode, artifact_root=artifact_root)  # type: ignore[arg-type]

    res = sess.execute_step_mock(prompt="hello", enforce_band_identity=True)
    assert res.status == "committed"

    # step dir exists with committed marker
    step_dir = Path(res.step_dir)
    assert (step_dir / "committed.ok").exists()
    assert (step_dir / "prompt.txt").exists()
    assert (step_dir / "conditioning_band.png").exists()
    assert (step_dir / "tile_full.png").exists()
    assert (step_dir / "new_half.png").exists()
    assert (step_dir / "canvas_before.png").exists()
    assert (step_dir / "canvas_after.png").exists()

    # canvas_latest advanced
    canvas = Image.open(Path(sess.state.session_root) / "canvas_latest.png")
    w, h = canvas.size
    if mode in ("x_ltr", "x_rtl"):
        assert h == TILE_PX
        assert w == TILE_PX + 512
    else:
        assert w == TILE_PX
        assert h == TILE_PX + 512