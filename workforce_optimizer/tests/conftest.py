# tests/conftest.py
import sys
import os
from pathlib import Path
import pytest
from tkinter import messagebox, filedialog
from datetime import date
from unittest.mock import patch
from lib.utils import user_data_dir

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    """Force save_input_data to save Employee Data directly to the passed temp path."""

    def patched_get_save_filename(default_path, file_type):
        if file_type == "Employee Data":
            print(f"DIRECT SAVE (fixture): Using temp path directly: {default_path}")
            return default_path  # No prompt, no remap
        # For other files, use original behavior (you can expand if needed)
        if os.path.exists(default_path):
            response = messagebox.askyesnocancel(
                f"File Exists: {file_type}",
                f"File already exists:\n{os.path.basename(default_path)}\n\n"
                f"Yes: Overwrite\nNo: Save As\nCancel: Skip"
            )
            if response is None:
                return False
            elif response:
                return default_path
            else:
                new_filename = filedialog.asksaveasfilename(
                    parent=None,
                    title=f"Save {file_type} As",
                    initialdir=user_data_dir(),
                    initialfile=os.path.basename(default_path),
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                return new_filename if new_filename else False
        return default_path

    # Patch the nested function inside save_input_data
    monkeypatch.setattr(
        'lib.gui_handlers.save_input_data.<locals>.get_save_filename',
        patched_get_save_filename
    )
    yield  

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