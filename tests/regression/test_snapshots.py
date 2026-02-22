import json
from pathlib import Path

import pytest

from ldi.app.runner import run_scenario
from utils import assert_json_like_close

SNAP_DIR = Path(__file__).parent / "snapshots"


@pytest.mark.xfail(strict=True, reason="run_scenario currently fails before producing model output due LDIModel invocation mismatch.")
def test_base_snapshot_via_real_runner_entrypoint(tmp_path):
    out = run_scenario(Path("runs/sample.json"), constants_file=Path("runs/constants.json"), assumptions_file="base_assumptions.json")
    expected = json.loads((SNAP_DIR / "base_scenario.json").read_text())
    assert_json_like_close(out, expected, atol=1e-6)
