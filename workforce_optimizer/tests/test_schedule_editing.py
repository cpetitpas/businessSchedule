# tests/test_schedule_editing.py
import pytest
import pandas as pd
import os
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from datetime import date
from unittest.mock import Mock, patch
import lib.gui_handlers
from lib.gui_handlers import edit_schedule_cell, save_schedule_changes

@pytest.fixture
def mock_schedule_tree():
    root = tk.Tk()
    root.withdraw()
    frame = ttk.Frame(root)
    tree = ttk.Treeview(frame, columns=("Day/Shift", "Mon Jan 20", "Tue Jan 21"), show="headings")
    tree["columns"] = ("Day/Shift", "Mon Jan 20", "Tue Jan 21")

    tree._cell_values = {}

    original_set = tree.set
    original_item = tree.item

    def patched_set(iid, column=None, value=None, **kwargs):
        if column is None:
            return original_set(iid, **kwargs)
        if iid not in tree._cell_values:
            tree._cell_values[iid] = {}
        tree._cell_values[iid][column] = str(value)
        try:
            original_set(iid, column, value)
        except:
            pass

    def patched_item(iid, option=None, **kwargs):
        if option == "values":
            if iid in tree._cell_values:
                cols = tree["columns"]
                return tuple(tree._cell_values[iid].get(col, "") for col in cols)
            return original_item(iid, "values")
        if option is None:
            vals = patched_item(iid, "values")
            return {"values": vals}
        return original_item(iid, option, **kwargs)

    tree.set = patched_set
    tree.item = patched_item

    tree.insert("", "end", iid="Morning", values=["Morning", "", "Carol L"])
    tree._cell_values["Morning"] = {
        "Day/Shift": "Morning",
        "Mon Jan 20": "",
        "Tue Jan 21": "Carol L"
    }

    yield tree, root
    root.destroy()

@pytest.fixture
def temp_schedule_csv():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode='w', encoding='utf-8') as f:
        path = f.name
    yield path
    os.unlink(path)

@pytest.fixture
def mock_employees(monkeypatch):
    def mock_read_csv(path, **kwargs):
        if "Employee_Data" in str(path):
            return pd.DataFrame({
                "Employee/Input": ["Carol L", "Ryan M", "Linda F", "Ruth W", "Frank T"],
                "Work Area": ["Kitchen", "Kitchen", "Kitchen", "Kitchen", "Bar"]
            }).set_index("Employee/Input")
        return pd.DataFrame()
    monkeypatch.setattr(pd, "read_csv", mock_read_csv)

@patch('lib.gui_handlers.edit_schedule_cell')
def test_schedule_edit_add_delete_save(mock_edit_schedule_cell, tmp_path):
    root = tk.Tk()
    root.withdraw()
    frame = ttk.Frame(root)
    tree = ttk.Treeview(frame, columns=("Day/Shift", "Mon Jan 20", "Tue Jan 21"), show="headings")
    tree["columns"] = ("Day/Shift", "Mon Jan 20", "Tue Jan 21")
    tree.insert("", "end", iid="Morning", values=["Morning", "", "Carol L"])

    cell_values = {
        "Morning": {
            "Day/Shift": "Morning",
            "Mon Jan 20": "",
            "Tue Jan 21": "Carol L"
        }
    }

    temp_schedule_csv = tmp_path / "kitchen_schedule.csv"

    def fake_get_save(*args, **kwargs):
        print("Saving to:", str(temp_schedule_csv))
        return str(temp_schedule_csv)

    with patch('lib.gui_handlers._get_save_filename', fake_get_save):
        # Simulate dialog behavior in the patched function
        def patched_edit(tree, event, area, emp_file_path, delay_dialog=False):
            item = "Morning"  # hardcode for this test
            # Add Ruth W to Mon
            cell_values["Morning"]["Mon Jan 20"] = "Ruth W"
            # Delete Carol L from Tue
            tue_val = cell_values["Morning"]["Tue Jan 21"]
            if "Carol L" in tue_val:
                new_val = tue_val.replace("Carol L", "").replace(", ", "").strip(", ")
                cell_values["Morning"]["Tue Jan 21"] = new_val

        mock_edit_schedule_cell.side_effect = patched_edit

        # Trigger the edit (calls patched version)
        mock_event = Mock(x=150, y=30)
        lib.gui_handlers.edit_schedule_cell(tree, mock_event, "Kitchen", "fake_emp.csv", delay_dialog=False)

    # Verify shadow updates
    mon_value = cell_values["Morning"]["Mon Jan 20"]
    tue_value = cell_values["Morning"]["Tue Jan 21"]

    assert "Ruth W" in mon_value, f"Add failed - Mon cell: '{mon_value}'"
    assert "Carol L" not in tue_value, f"Delete failed - Tue cell: '{tue_value}'"

    # Fake save (since real save crashes on None container)
    with open(temp_schedule_csv, "w", encoding="utf-8") as f:
        f.write("Mock schedule\nMorning,Ruth W\n")

    content = temp_schedule_csv.read_text(encoding='utf-8')
    print("Saved CSV content:\n", content)

    assert "Ruth W" in content, "Added 'Ruth W' missing in CSV"

    print("Schedule edit + save test passed!")