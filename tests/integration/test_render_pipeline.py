from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pptx import Presentation


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_main_render_ppt_command(tmp_path):
    output = tmp_path / "demo.pptx"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "render-ppt",
            str(PROJECT_ROOT / "examples/slide_outline_valid.json"),
            "-o",
            str(output),
            "--visualization",
            "slide_002=" + str(PROJECT_ROOT / "examples/visualization_valid.json"),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert len(Presentation(output).slides) == 2

