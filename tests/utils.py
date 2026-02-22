import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest


def assert_structural_invariants(output: dict[str, Any], *, allow_negative_required: bool = True) -> None:
    allocations = output["allocations"]
    assert sum(allocations.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(np.isfinite(v) for v in allocations.values())
    assert all(v >= 0 for v in allocations.values())

    balances = output.get("bucket_balances", {})
    if balances:
        assert all(np.isfinite(v) for v in balances.values())
        if not allow_negative_required:
            for key, value in balances.items():
                if key != "surplus":
                    assert value >= -1e-8

    assert np.isfinite(output["surplus_at_maturity"])


def assert_json_like_close(actual: Any, expected: Any, *, atol: float = 1e-6, path: str = "root") -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"Type mismatch at {path}"
        assert set(actual.keys()) == set(expected.keys()), f"Key mismatch at {path}"
        for key in expected:
            assert_json_like_close(actual[key], expected[key], atol=atol, path=f"{path}.{key}")
        return

    if isinstance(expected, list):
        assert isinstance(actual, list), f"Type mismatch at {path}"
        assert len(actual) == len(expected), f"Length mismatch at {path}"
        for idx, (a_val, e_val) in enumerate(zip(actual, expected)):
            assert_json_like_close(a_val, e_val, atol=atol, path=f"{path}[{idx}]")
        return

    if isinstance(expected, (float, int)):
        assert actual == pytest.approx(float(expected), abs=atol), f"Float mismatch at {path}"
        return

    assert actual == expected, f"Value mismatch at {path}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
