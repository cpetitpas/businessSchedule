import pytest
from pathlib import Path
from datetime import date
from lib.data_loader import load_csv
import logging


def test_load_csv_success(sample_paths, sample_start_date, sample_num_weeks):
    result = load_csv(
        sample_paths["emp"],
        sample_paths["req"],
        sample_paths["limits"],
        sample_start_date,
        sample_num_weeks
    )
    assert result is not None, "load_csv returned None"

    employees, days, shifts, areas, *_ = result
    assert len(employees) > 0
    assert len(shifts) == 3
    assert len(areas) == 3
    assert all(d in days for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])


def test_load_csv_missing_file(caplog):
    """Test that missing file logs error but does NOT crash app (as per your code)"""
    with caplog.at_level(logging.ERROR):
        result = load_csv("nonexistent.csv", "dummy", "dummy", None, 1)
        assert result is None, "Should return None on missing file"
        assert "No such file or directory" in caplog.text


def test_load_csv_invalid_format(tmp_path, caplog):
    """Test malformed CSV → logs error, returns None"""
    bad_csv = tmp_path / "Employee_Data_broken.csv"
    bad_csv.write_text(
        "Employee/Input,Name1\n"
        "Work Area,Bar\n"
        "BrokenRow,,,\n"  # mismatched fields
    )

    with caplog.at_level(logging.ERROR):
        result = load_csv(str(bad_csv), "dummy", "dummy", None, 1)
        assert result is None
        assert "Error tokenizing data" in caplog.text or "Failed to load CSV" in caplog.text


def test_employees_are_sorted_alphabetically(sample_paths, sample_start_date, sample_num_weeks):
    result = load_csv(*sample_paths.values(), sample_start_date, sample_num_weeks)
    employees = result[0]
    assert employees == sorted(employees, key=str.lower)