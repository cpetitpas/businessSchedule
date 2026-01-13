# tests/test_solver_golden.py
import json
from pathlib import Path
from lib.data_loader import load_csv
from lib.solver import solve_schedule

GOLDEN_PATH = Path(__file__).parent / "golden" / "schedule_golden_2025-12-01.json"


def test_solver_golden_output(sample_paths, sample_start_date, sample_num_weeks):
    result = load_csv(
        sample_paths["emp"],
        sample_paths["req"],
        sample_paths["limits"],
        sample_start_date,
        sample_num_weeks
    )
    assert result is not None

    prob, x, result_dict = solve_schedule(*result, sample_start_date, num_weeks=sample_num_weeks)

    # Clean output (remove timestamps, paths, etc.)
    cleaned = {}
    for key, value in result_dict.items():
        if isinstance(value, list) and value and isinstance(value[0], tuple):
            # schedule lists → keep only stable parts
            cleaned[key] = [tuple(item[:4]) for item in value]  # employee, date, day, shift
        else:
            cleaned[key] = value

    current = json.dumps(cleaned, sort_keys=True, indent=2)

    if GOLDEN_PATH.exists():
        expected = GOLDEN_PATH.read_text(encoding="utf-8")
        assert current == expected, "Solver output changed! Check if intentional."
    else:
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(current, encoding="utf-8")
        pytest.fail("Golden file created. Re-run test to verify.")