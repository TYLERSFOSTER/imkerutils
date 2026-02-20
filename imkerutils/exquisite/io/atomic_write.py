from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable, Union


PathLike = Union[str, Path]


def _fsync_dir(dirpath: Path) -> None:
    """
    Best-effort directory fsync for durability. On macOS this usually works.
    """
    try:
        fd = os.open(str(dirpath), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def atomic_write_bytes(path: PathLike, data: bytes) -> None:
    """
    Atomically replace `path` with `data`:
      - write temp file in same directory
      - fsync temp
      - os.replace into place
      - fsync directory (best-effort)
    """
    dst = Path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(dir=str(dst.parent), prefix=dst.name + ".", suffix=".tmp", delete=False) as f:
        tmp_path = Path(f.name)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, dst)
    _fsync_dir(dst.parent)


def atomic_write_text(path: PathLike, text: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_with(path: PathLike, writer: Callable[[Path], None]) -> None:
    """
    Atomically write a file produced by `writer(tmp_path)` into `path`.
    Useful for Pillow Image.save or other "write to filename" APIs.
    """
    dst = Path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(dir=str(dst.parent), prefix=dst.name + ".", suffix=".tmp", delete=False) as f:
        tmp_path = Path(f.name)

    try:
        writer(tmp_path)
        try:
            fd = os.open(str(tmp_path), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass

        os.replace(tmp_path, dst)
        _fsync_dir(dst.parent)
    finally:
        # if writer failed, clean up temp
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass