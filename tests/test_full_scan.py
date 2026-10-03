import json
from pathlib import Path

from src.full_scan import render, scan


def test_scan_reports_file_line_and_static_status(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text("def run():\n    except Exception:\n        pass\n", encoding="utf-8")
    findings = scan(tmp_path)
    assert findings
    assert findings[0].location == "sample.py:2"
    assert findings[0].status == "STATIC-RISK"
    assert "Root Cause proven" in render(findings, root=tmp_path, mode="strict")


def test_ci_json_is_machine_readable(tmp_path: Path):
    output = render(scan(tmp_path), root=tmp_path, mode="ci", json_output=True)
    assert json.loads(output)["mode"] == "ci"
