# tests/test_employee_editing.py
import pytest
import pandas as pd
import os
import shutil
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from lib.gui_handlers import display_input_data, save_input_data, tree_to_df


@pytest.fixture
def temp_employee_csv():
    original = Path("tests/data/Employee_Data.csv")
    assert original.exists()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dest = tmp_path / "Employee_Data.csv"
        shutil.copy2(original, dest)
        yield str(dest)


@pytest.fixture
def temp_req_csv():
    content = """Day/Area,Sun,Mon,Tue,Wed,Thu,Fri,Sat
Bar,1/1/1,1/0/1,1/0/1,1/0/1,1/0/1,1/1/1,1/1/1
Kitchen,1/1/2,1/0/2,1/0/2,1/0/2,1/0/2,1/1/2,1/1/2
Dish,0/0/1,0/0/1,0/0/1,0/0/1,0/0/1,0/0/1,0/0/1"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def temp_limits_csv():
    content = """Max Number of Shifts per Day,Violate Rules Order,Shifts,Work Areas
1,"Preferred Days, Preferred Shift, Max Number of Weekend Days, Min Shifts per Week","Morning, Midday, Evening","Kitchen, Bar, Dish"
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def mock_tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_tree_to_df_roundtrip(temp_employee_csv):
    df_original = pd.read_csv(temp_employee_csv)
    root = tk.Tk()
    root.withdraw()
    frame = ttk.Frame(root)

    tree = None
    def fake_display(*args, **kwargs):
        nonlocal tree
        from lib.gui_handlers import create_treeview
        tree = create_treeview(frame, temp_employee_csv, has_index=False)

    fake_display()

    assert tree is not None
    df_from_tree = tree_to_df(tree, has_index=False)

    cols = ['Employee/Input'] + sorted(c for c in df_original.columns if c != 'Employee/Input')
    df_original_sorted = df_original[cols].replace({pd.NA: '', float('nan'): ''})
    df_from_tree_sorted = df_from_tree[cols].replace({pd.NA: '', float('nan'): ''})

    pd.testing.assert_frame_equal(
        df_original_sorted.reset_index(drop=True),
        df_from_tree_sorted.reset_index(drop=True),
        check_dtype=False,
        check_exact=False,
        check_like=True,
        check_column_type=False
    )


def test_display_save_reload_cycle(
    temp_employee_csv,
    temp_req_csv,
    temp_limits_csv,
    mock_tk_root
):
    root = mock_tk_root

    emp_frame = ttk.Frame(root)
    req_frame = ttk.Frame(root)
    limits_frame = ttk.Frame(root)
    notebook = ttk.Notebook(root)
    summary_text = tk.Text(root)

    emp_var = tk.StringVar(value=temp_employee_csv)
    req_var = tk.StringVar(value=temp_req_csv)
    limits_var = tk.StringVar(value=temp_limits_csv)

    display_input_data(
        emp_var.get(),
        req_var.get(),
        limits_var.get(),
        emp_frame,
        req_frame,
        limits_frame,
        root,
        notebook,
        summary_text
    )

    root.update_idletasks()
    emp_frame.update_idletasks()

    emp_tree = None
    for widget in emp_frame.winfo_children():
        if isinstance(widget, ttk.Frame):
            for sub in widget.winfo_children():
                if isinstance(sub, ttk.Treeview):
                    emp_tree = sub
                    break
        if emp_tree:
            break

    assert emp_tree is not None, "Could not find Employee Data Treeview"

    # Force full realization
    emp_tree.update()
    root.update()
    emp_frame.update_idletasks()

    assert "Carol L" in emp_tree["columns"], \
           f"Carol L not found in columns. Available: {emp_tree['columns']}"

    carol_column = "Carol L"
    carol_idx = emp_tree["columns"].index(carol_column)

    must_off_iid = max_shifts_iid = None
    for iid in emp_tree.get_children():
        values = emp_tree.item(iid, "values")
        if not values:
            continue
        row_label = values[0].strip()
        if row_label == "Must have off":
            must_off_iid = iid
        elif row_label == "Max Shifts per Week":
            max_shifts_iid = iid

    assert must_off_iid is not None, "Row 'Must have off' not found"
    assert max_shifts_iid is not None, "Row 'Max Shifts per Week' not found"

    # Update
    must_off_values = list(emp_tree.item(must_off_iid, "values"))
    max_shifts_values = list(emp_tree.item(max_shifts_iid, "values"))

    must_off_values[carol_idx] = "01/25/2026,01/26/2026"
    max_shifts_values[carol_idx] = "4"

    emp_tree.item(must_off_iid, values=must_off_values)
    emp_tree.item(max_shifts_iid, values=max_shifts_values)

    # Debug confirmation
    print("After update - Must have off for Carol L:", 
          emp_tree.item(must_off_iid, "values")[carol_idx])
    print("After update - Max Shifts for Carol L:", 
          emp_tree.item(max_shifts_iid, "values")[carol_idx])

    # Final force sync before save
    root.update()
    emp_tree.update_idletasks()

    save_input_data(
        emp_var,
        req_var,
        limits_var,
        emp_frame,
        req_frame,
        limits_frame,
        root
    )

    print(f"Test is reading back from: {temp_employee_csv}")
    print("First few lines of saved file:")
    with open(temp_employee_csv, 'r') as f:
        print('\n'.join(f.readline().strip() for _ in range(5)))

    df_after = pd.read_csv(temp_employee_csv)

    must_off_row = df_after[df_after["Employee/Input"].str.strip() == "Must have off"].iloc[0]
    max_shifts_row = df_after[df_after["Employee/Input"].str.strip() == "Max Shifts per Week"].iloc[0]

    assert must_off_row["Carol L"].strip() == "01/25/2026,01/26/2026", \
           f"Expected new date, got: {must_off_row['Carol L']}"

    assert str(max_shifts_row["Carol L"]).strip() == "4", \
           f"Expected 4, got: {max_shifts_row['Carol L']}"
