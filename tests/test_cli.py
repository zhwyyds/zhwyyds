"""CLI 命令测试（IT1-1，补 CLI 0% 覆盖）。"""

import json
from pathlib import Path

import pytest

from data_governance import __version__
from data_governance.cli import main


def test_version_command(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_unknown_command_exits():
    with pytest.raises(SystemExit):
        main(["nonsense"])


def test_acceptance_run_writes_report(mini_project: Path, capsys):
    code = main(["acceptance", "run", "--base-dir", str(mini_project)])
    assert code == 0
    out = capsys.readouterr().out
    assert "total=" in out
    reports = list((mini_project / "scoring").glob("acceptance_report_*.md"))
    assert reports, "应生成验收报告文件"


def test_acceptance_run_json_output(mini_project: Path, capsys):
    code = main(["acceptance", "run", "--base-dir", str(mini_project), "--json"])
    assert code == 0
    out = capsys.readouterr().out
    # --json 输出为 indent=2 的多行 JSON，从第一个 "{" 提取
    start = out.index("{")
    payload = json.loads(out[start:])
    assert {"total", "grade", "veto", "dimensions"} <= set(payload.keys())
