"""Regression test: scanner must not leak file handles (ResourceWarning)."""
import sys
import tempfile
import warnings
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from scanner import _component_for  # noqa: E402


def test_component_for_does_not_leak_file():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "sample.py"
        p.write_text("def f():\n    return 1\n")
        # Any leaked handle would raise ResourceWarning here.
        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)
            comp = _component_for(p, p.relative_to(d))
    assert comp["lines"] == 2
    assert comp["type"] == "python"
