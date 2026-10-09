import json
from pathlib import Path

from datetime import datetime

from src.full_scan import render, scan, write_report_bundle


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


def test_report_bundle_uses_date_and_mode_directories(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text("except Exception:\n    pass\n", encoding="utf-8")
    markdown_path, json_path = write_report_bundle(
        scan(tmp_path),
        root=tmp_path,
        mode="strict",
        now=datetime(2026, 10, 9, 12, 30),
    )
    assert markdown_path == tmp_path / "docs" / "2026-10-09" / "reports" / "strict" / "report.md"
    assert json_path == markdown_path.with_name("report.json")
    assert (tmp_path / "docs" / "2026-10-09" / "README.md").exists()
    assert "Full Scan" in markdown_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["mode"] == "strict"
