# tests/conftest.py
import pytest
import pandas as pd
from pathlib import Path
from lib.data_loader import load_csv
from tkinter import messagebox

TEST_DATA = Path(__file__).parent / "data"


@pytest.fixture
def sample_paths():
    return {
        "emp": str(TEST_DATA / "Employee_Data.csv"),
        "req": str(TEST_DATA / "Personnel_Required.csv"),
        "limits": str(TEST_DATA / "Hard_Limits.csv"),
    }


@pytest.fixture
def sample_start_date():
    from datetime import date
    return date(2025, 12, 14)


@pytest.fixture
def sample_num_weeks():
    return 2

@pytest.fixture(autouse=True)
def mock_messageboxes(mocker):
    mocker.patch.object(messagebox, 'showerror')
    mocker.patch.object(messagebox, 'showwarning')
    mocker.patch.object(messagebox, 'showinfo')
    yield