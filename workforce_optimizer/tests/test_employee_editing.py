# tests/test_employee_editing.py
import pytest
import tkinter as tk
from tkinter import ttk
from lib.gui_handlers import on_tree_double_click
from unittest.mock import patch

# SET TO True when you want to tune coordinates
# SET TO False for normal fast test runs
DEBUG_WINDOW = False


@pytest.fixture(scope="function")
def visible_root():
    root = tk.Tk()
    root.title("Test Treeview")
    root.geometry("900x600+100+100")
    root.deiconify()  # Make visible - necessary for reliable identify/bbox
    yield root
    root.destroy()


@pytest.fixture
def sample_tree(visible_root):
    tree = ttk.Treeview(visible_root, columns=["Employee/Input", "Anthony F", "Carol L"], show="headings")
    tree.heading("Employee/Input", text="Employee/Input")
    tree.heading("Anthony F", text="Anthony F")
    tree.heading("Carol L", text="Carol L")

    tree.insert("", "end", iid="must_off", values=["Must have off", "11/13/2025", ""])
    tree.insert("", "end", iid="max_shifts", values=["Max Shifts per Week", "3", "4"])

    tree.pack(fill="both", expand=True)
    visible_root.update_idletasks()
    visible_root.update()

    return tree


def test_edit_must_have_off(visible_root, sample_tree, mocker):
    # === DEBUG MODE - OPENS WINDOW AND SHOWS COORDINATES ===
    if DEBUG_WINDOW:
        print("\n" + "="*80)
        print("DEBUG MODE ACTIVE")
        print("Window is open. Do the following:")
        print("  1. Move mouse over the cell you want to edit")
        print("  2. Console shows live x/y")
        print("  3. Double-click the cell — console shows DOUBLE-CLICK DETECTED + coordinates")
        print("  4. Use those exact x/y below in the event = line")
        print("  5. Close window when done")
        print("="*80 + "\n")

        def show_live_coords(event):
            print(f"Live mouse: x={event.x}, y={event.y}")

        def on_double_click(event):
            row = sample_tree.identify_row(event.y)
            col = sample_tree.identify_column(event.x)
            print(f"\nDOUBLE-CLICK DETECTED!")
            print(f"  x={event.x}, y={event.y}")
            print(f"  Row iid: {row}")
            print(f"  Column: {col}")
            print("  → Use these x/y in the MockEvent below!\n")

        sample_tree.bind("<Motion>", show_live_coords)
        sample_tree.bind("<Double-1>", on_double_click)
        visible_root.bind("<Double-1>", on_double_click)  # fallback

        visible_root.deiconify()
        visible_root.title("DEBUG - Double-click cell - Close when ready")
        visible_root.mainloop()
        print("Window closed - continuing test...\n")

    # === REAL SIMULATION - USE YOUR TUNED COORDINATES HERE ===
    # Replace these with the values from the double-click print above
    event = type("MockEvent", (), {"x": 616, "y": 37})

    # Run the handler
    on_tree_double_click(sample_tree, event, has_index=False)

    # Give Tkinter time to create Entry
    visible_root.update()

    # Find real Entry widget
    entry_widget = None
    for child in visible_root.winfo_children():
        if isinstance(child, tk.Entry):
            entry_widget = child
            break

    if entry_widget is None:
        pytest.fail("No Entry created - coordinates missed cell. Re-run with DEBUG_WINDOW=True to tune.")

    # Set value and trigger Return
    entry_widget.delete(0, tk.END)
    entry_widget.insert(0, "01/20/2026, 01/21/2026")
    entry_widget.event_generate("<Return>")

    visible_root.update()
    print(sample_tree.identify_row(37))

    updated = sample_tree.set("must_off", "Carol L")
    assert updated == "01/20/2026, 01/21/2026", f"Got {updated}"


def test_edit_max_shifts_carol(visible_root, sample_tree, mocker):
    if DEBUG_WINDOW:
        print("\n" + "="*80)
        print("DEBUG MODE - MAX SHIFTS TEST")
        print("Double-click the 'Max Shifts per Week' cell under Carol L")
        print("="*80 + "\n")

        def show_live(event):
            print(f"Live: x={event.x}, y={event.y}")

        def on_dc(event):
            row = sample_tree.identify_row(event.y)
            col = sample_tree.identify_column(event.x)
            print(f"DOUBLE-CLICK! x={event.x}, y={event.y} | Row: {row} | Col: {col}")

        sample_tree.bind("<Motion>", show_live)
        sample_tree.bind("<Double-1>", on_dc)

        visible_root.deiconify()
        visible_root.mainloop()

    # Use your tuned coordinates here
    event = type("MockEvent", (), {"x": 612, "y": 53})

    on_tree_double_click(sample_tree, event, has_index=False)

    visible_root.update()

    entry_widget = None
    for child in visible_root.winfo_children():
        if isinstance(child, tk.Entry):
            entry_widget = child
            break

    if entry_widget is None:
        pytest.fail("No Entry - missed cell")

    entry_widget.delete(0, tk.END)
    entry_widget.insert(0, "5")
    entry_widget.event_generate("<Return>")

    visible_root.update()

    updated = sample_tree.set("max_shifts", "Carol L")
    assert updated == "5", f"Got {updated}"