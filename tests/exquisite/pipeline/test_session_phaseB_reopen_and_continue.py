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
def test_reopen_and_continue_two_steps(tmp_path: Path, mode: str) -> None:
    initial = tmp_path / "initial.png"
    _write_initial_canvas(initial)

    artifact_root = tmp_path / "_generated" / "exquisite"
    sess = ExquisiteSession.create(initial_canvas_path=initial, mode=mode, artifact_root=artifact_root)  # type: ignore[arg-type]

    res1 = sess.execute_step_mock(prompt="step1")
    assert res1.status == "committed"

    # reopen
    root = Path(sess.state.session_root)
    sess2 = ExquisiteSession.open(session_root=root)

    res2 = sess2.execute_step_mock(prompt="step2")
    assert res2.status == "committed"

    # ensure step dirs exist
    assert (root / "steps" / "0001" / "committed.ok").exists()
    assert (root / "steps" / "0002" / "committed.ok").exists()

    # size should reflect 2 steps
    canvas = Image.open(root / "canvas_latest.png")
    w, h = canvas.size
    if mode in ("x_ltr", "x_rtl"):
        assert h == TILE_PX
        assert w == TILE_PX + 2 * 512
    else:
        assert w == TILE_PX
        assert h == TILE_PX + 2 * 512