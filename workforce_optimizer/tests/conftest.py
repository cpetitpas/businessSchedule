# tests/conftest.py
import sys
import os
from pathlib import Path
import pytest
from tkinter import messagebox, filedialog, ttk
from datetime import date
from unittest.mock import patch
from lib.gui_handlers import tree_to_df
import lib.gui_handlers

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

@pytest.fixture(autouse=True)
def reset_gui_globals():
    """Reset GUI-related globals before/after the editing test to prevent leakage"""
    from lib.gui_handlers import all_input_trees, all_listboxes
    all_input_trees.clear()
    all_listboxes.clear()
    yield
    all_input_trees.clear()
    all_listboxes.clear()

@pytest.fixture(scope="session")
def sample_paths():
    base = Path("tests/data")
    return {
        "emp": str(base / "Employee_Data.csv"),
        "req": str(base / "Personnel_Required.csv"),
        "limits": str(base / "Hard_Limits.csv"),
    }

@pytest.fixture(scope="session")
def sample_start_date():
    return date(2025, 12, 14)  

@pytest.fixture(scope="session")
def sample_num_weeks():
    return 2

@pytest.fixture
def direct_employee_save(monkeypatch):
    print("FIXTURE ACTIVATED: direct_employee_save is running!")
    monkeypatch.setenv("TEST_DIRECT_SAVE", "1")
    yield
    monkeypatch.delenv("TEST_DIRECT_SAVE", raising=False) 

@pytest.fixture(autouse=True)
def no_messagebox(monkeypatch):
    """Prevent all tkinter messagebox calls during tests"""
    def fake_yesnocancel(title, message, **kwargs):
        # For "File exists - Overwrite?" we always choose Yes (overwrite)
        if "File already exists" in message:
            return True  # Yes → overwrite
        return None  # or False/Cancel for others

    def fake_showinfo(*args, **kwargs):
        pass  # silent

    def fake_showerror(*args, **kwargs):
        pass

    monkeypatch.setattr(messagebox, "askyesnocancel", fake_yesnocancel)
    monkeypatch.setattr(messagebox, "showinfo", fake_showinfo)
    monkeypatch.setattr(messagebox, "showerror", fake_showerror)
    monkeypatch.setattr(messagebox, "showwarning", fake_showinfo)