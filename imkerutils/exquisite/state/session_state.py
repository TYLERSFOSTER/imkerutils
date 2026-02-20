from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional

ExtendMode = Literal["x_ltr", "x_rtl", "y_ttb", "y_btt"]


@dataclass
class SessionState:
    # identity / location
    session_id: str
    session_root: str  # absolute path

    # authoritative canvas pointer
    canvas_filename: str = "canvas_latest.png"
    session_state_filename: str = "session_state.json"

    # mode
    mode: ExtendMode = "x_ltr"

    # tile-mode params (Phase B still fixed)
    tile_px: int = 1024
    ext_px: int = 512
    band_px: int = 512

    # expected canvas dims (advisory expectation; checked against Pillow header)
    canvas_width_px_expected: int = 1024
    canvas_height_px_expected: int = 1024

    # step tracking
    step_index_current: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_root": self.session_root,
            "canvas_filename": self.canvas_filename,
            "session_state_filename": self.session_state_filename,
            "mode": self.mode,
            "tile_px": self.tile_px,
            "ext_px": self.ext_px,
            "band_px": self.band_px,
            "canvas_width_px_expected": self.canvas_width_px_expected,
            "canvas_height_px_expected": self.canvas_height_px_expected,
            "step_index_current": self.step_index_current,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SessionState":
        return cls(
            session_id=str(d["session_id"]),
            session_root=str(d["session_root"]),
            canvas_filename=str(d.get("canvas_filename", "canvas_latest.png")),
            session_state_filename=str(d.get("session_state_filename", "session_state.json")),
            mode=d.get("mode", "x_ltr"),
            tile_px=int(d.get("tile_px", 1024)),
            ext_px=int(d.get("ext_px", 512)),
            band_px=int(d.get("band_px", 512)),
            canvas_width_px_expected=int(d.get("canvas_width_px_expected", 1024)),
            canvas_height_px_expected=int(d.get("canvas_height_px_expected", 1024)),
            step_index_current=int(d.get("step_index_current", 0)),
        )

    @property
    def root_path(self) -> Path:
        return Path(self.session_root)

    @property
    def canvas_path(self) -> Path:
        return self.root_path / self.canvas_filename

    @property
    def state_path(self) -> Path:
        return self.root_path / self.session_state_filename

    def step_dir(self, step_index: int) -> Path:
        return self.root_path / "steps" / f"{step_index:04d}"