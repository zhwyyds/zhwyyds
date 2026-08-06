"""跨平台文件锁 — Unix 用 fcntl.flock，Windows 用 msvcrt.locking。

背景：文件锁用于防止多进程并发写入 CSV/JSON 时丢数据。fcntl 是 Unix
专属模块，Windows 无此模块；此处按平台分发，对外保持同一 file_lock() 接口。
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """对 path 加排他文件锁（锁文件为 path.with_suffix(path.suffix + ".lock")）。

    Unix: fcntl.flock(LOCK_EX / LOCK_UN)，阻塞式；
    Windows: msvcrt.locking(LK_LOCK / LK_UNLCK)，锁定 1 字节，最多重试约 10 秒。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    if os.name == "nt":
        import msvcrt

        # msvcrt.locking 锁定的字节范围不能超出文件末尾，须保证锁文件非空
        with lock_path.open("a+b") as lock_fd:
            lock_fd.seek(0)
            if lock_fd.read(1) == b"":
                lock_fd.write(b"\x00")
                lock_fd.flush()
            lock_fd.seek(0)
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl  # type: ignore[import-not-found]

        # fcntl 为 Unix 专属模块，Windows 平台的 mypy stub 无 flock 属性，按 attr-defined 忽略
        _flock = fcntl.flock  # type: ignore[attr-defined]
        _lock_ex = fcntl.LOCK_EX  # type: ignore[attr-defined]
        _lock_un = fcntl.LOCK_UN  # type: ignore[attr-defined]

        with lock_path.open("w") as lock_fd:
            _flock(lock_fd, _lock_ex)
            try:
                yield
            finally:
                _flock(lock_fd, _lock_un)
