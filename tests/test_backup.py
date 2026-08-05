"""备份脚本测试（IT1-3）。"""

import os
import subprocess
from pathlib import Path


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


def test_backup_script_snapshots_data_dirs(tmp_path: Path, project_root: Path):
    script = project_root / "scripts" / "backup.sh"
    assert script.is_file(), "scripts/backup.sh 应存在"

    # 构造一个带数据的临时项目
    for rel in ("config", "roots", "metrics", "lineage", "reviews"):
        _touch(tmp_path / rel / "sample.csv")

    result = subprocess.run(
        ["bash", str(script), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "backup done:" in result.stdout

    # backup 下应有一份时间戳快照，且包含数据目录
    backup_root = tmp_path / "backup"
    snapshots = [p for p in backup_root.iterdir() if p.is_dir()]
    assert len(snapshots) == 1
    snap = snapshots[0]
    for rel in ("config", "roots", "metrics", "lineage", "reviews"):
        assert (snap / rel / "sample.csv").is_file(), f"快照缺少 {rel}"


def test_backup_script_skips_missing_dirs(tmp_path: Path, project_root: Path):
    script = project_root / "scripts" / "backup.sh"
    # 项目里只有 config 一个目录，其余缺失不应报错
    (tmp_path / "config").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(script), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    snap = next((tmp_path / "backup").iterdir())
    assert (snap / "config").is_dir()
    assert not (snap / "roots").exists()


def test_backup_script_cleanup_old_snapshots(tmp_path: Path, project_root: Path):
    script = project_root / "scripts" / "backup.sh"
    (tmp_path / "config").mkdir(parents=True)

    # 造一个过期快照（改 mtime 到 10 天前），KEEP_DAYS=7 时应被清理
    old = tmp_path / "backup" / "2026-07-01_000000"
    old.mkdir(parents=True)
    (old / "config").mkdir()
    stamp = 10 * 24 * 3600
    os.utime(old, (stamp, stamp))

    result = subprocess.run(
        ["bash", str(script), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "KEEP_DAYS": "7"},
    )
    assert result.returncode == 0, result.stderr
    remaining = [p for p in (tmp_path / "backup").iterdir() if p.is_dir()]
    assert len(remaining) == 1, f"过期快照应被清理，剩余: {remaining}"
