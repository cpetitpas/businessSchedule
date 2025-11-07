import math
import os
import json
import appdirs
from pathlib import Path
from datetime import datetime, timedelta
import logging
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox

# ------------------------------------------------------------------
# Helper – where the JSON file lives
# ------------------------------------------------------------------
def _settings_path() -> Path:
    cfg_dir = Path(appdirs.user_config_dir(appname="Workforce Optimizer", appauthor=False))
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "settings.json"

# ------------------------------------------------------------------
# Load (or create) the JSON dict
# ------------------------------------------------------------------
def _load_settings() -> dict:
    p = _settings_path()
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning(f"Failed to read settings file: {e}")
    # default values
    return {}

# ------------------------------------------------------------------
# Save the JSON dict
# ------------------------------------------------------------------
def _save_settings(data: dict):
    p = _settings_path()
    try:
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logging.error(f"Could not write settings file: {e}")

# ------------------------------------------------------------------
# Public API – data directory
# ------------------------------------------------------------------
def user_data_dir() -> str:
    """
    Returns the folder that holds CSVs (default: %LOCALAPPDATA%\\Workforce Optimizer\\data)
    The user can override it in Settings → Data folder.
    """
    settings = _load_settings()
    custom = settings.get("data_dir")
    if custom and Path(custom).is_dir():
        return str(Path(custom) / "data")
    # fallback
    path = Path(appdirs.user_data_dir(appname='Workforce Optimizer', appauthor=False)) / "data"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)

# ------------------------------------------------------------------
# Public API – output directory
# ------------------------------------------------------------------
def user_output_dir() -> str:
    """
    Returns the folder for generated schedules / reports
    (default: %LOCALAPPDATA%\\Workforce Optimizer\\output)
    """
    settings = _load_settings()
    custom = settings.get("output_dir")
    if custom and Path(custom).is_dir():
        return str(Path(custom) / "output")
    path = Path(appdirs.user_data_dir(appname='Workforce Optimizer', appauthor=False)) / "output"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)

# ------------------------------------------------------------------
# UI – Settings dialog (called from main.py)
# ------------------------------------------------------------------
def show_settings_dialog(parent: tk.Tk):
    """
    Modal dialog that lets the user pick a new data / output root folder.
    The selected folder will contain the sub-folders ``data`` and ``output``.
    """
    dlg = tk.Toplevel(parent)
    dlg.title("Settings – Folder Locations")
    dlg.geometry("680x180")
    dlg.transient(parent)
    dlg.grab_set()
    dlg.resizable(False, False)

    # Set icon to match standard dialogs
    try:
        from main import resource_path  # Import from main.py
        dlg.iconbitmap(resource_path(r'icons\teamwork.ico'))
    except Exception as e:
        # Fallback: use default
        pass

    # current values
    cur_data_root   = Path(user_data_dir()).parent
    cur_output_root = Path(user_output_dir()).parent

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    pad = dict(padx=10, pady=5)

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)

    # Data folder
    ttk.Label(frm, text="Data folder (contains *.csv files):").grid(row=0, column=0, sticky="w", **pad)
    data_var = tk.StringVar(value=str(cur_data_root))
    ttk.Entry(frm, textvariable=data_var, width=50).grid(row=0, column=1, **pad)
    
    def browse_data_folder():
        folder = filedialog.askdirectory(
            initialdir=data_var.get(),
            title="Select folder that will hold the 'data' sub-folder",
            parent=dlg
        )
        if folder:
            data_var.set(folder)
    
    ttk.Button(frm, text="Browse…", command=browse_data_folder).grid(row=0, column=2, **pad)

    # Output folder
    ttk.Label(frm, text="Output folder (schedules, reports):").grid(row=1, column=0, sticky="w", **pad)
    out_var = tk.StringVar(value=str(cur_output_root))
    ttk.Entry(frm, textvariable=out_var, width=50).grid(row=1, column=1, **pad)
    
    def browse_output_folder():
        folder = filedialog.askdirectory(
            initialdir=out_var.get(),
            title="Select folder that will hold the 'output' sub-folder",
            parent=dlg
        )
        if folder:
            out_var.set(folder)
    
    ttk.Button(frm, text="Browse…", command=browse_output_folder).grid(row=1, column=2, **pad)

    # Buttons
    btn_frm = ttk.Frame(frm)
    btn_frm.grid(row=2, column=0, columnspan=3, pady=15)

    def apply():
        new_data   = Path(data_var.get().strip())
        new_output = Path(out_var.get().strip())

        # sanity checks
        if not new_data.is_dir():
            messagebox.showerror("Invalid folder", "Data folder does not exist.", parent=dlg)
            return
        if not new_output.is_dir():
            messagebox.showerror("Invalid folder", "Output folder does not exist.", parent=dlg)
            return

        # write JSON
        _save_settings({"data_dir": str(new_data), "output_dir": str(new_output)})

        # recreate sub-folders if they vanished
        (new_data / "data").mkdir(parents=True, exist_ok=True)
        (new_output / "output").mkdir(parents=True, exist_ok=True)

        messagebox.showinfo("Settings saved",
                            "Folder locations updated.\n"
                            "The application will use the new paths from now on.",
                            parent=dlg)
        dlg.destroy()

    ttk.Button(btn_frm, text="Apply", command=apply).pack(side="left", padx=5)
    ttk.Button(btn_frm, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

    # centre on parent
    dlg.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (dlg.winfo_width() // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (dlg.winfo_height() // 2)
    dlg.geometry(f"+{x}+{y}")

    parent.wait_window(dlg)

def user_log_dir() -> str:
    """
    Returns:  %LOCALAPPDATA%\Workforce Optimizer\logs
    """
    path = os.path.join(appdirs.user_data_dir(appname='Workforce Optimizer', appauthor=False), 'logs')
    os.makedirs(path, exist_ok=True)
    return path


def find_treeviews(widget):
    """
    Recursively find all ttk.Treeview widgets in the widget and its descendants.
    """
    treeviews = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Treeview):
            treeviews.append(child)
        else:
            treeviews.extend(find_treeviews(child))
    return treeviews

def min_employees_to_avoid_weekend_violations(
        max_weekend_days, areas, violations, work_areas, employees,
        start_date=None, num_weeks=None, result_dict=None):
    """
    Return:
        required_employees (dict area to int)
        summary_text (str)
        violations (list of str)   # now always populated
    """
    # -------------------------------------------------
    # 1. If we have a solved schedule to build violations from it
    # -------------------------------------------------
    if not violations and result_dict and start_date and num_weeks:
        end_date = start_date + timedelta(days=7 * num_weeks - 1)
        # Build a list of **complete** Fri-Sat-Sun triplets that fall **entirely** inside the schedule
        weekends = []  # each entry = [(week, day_idx), ...] for Fri-Sat-Sun
        cur = start_date - timedelta(days=6)  # start far enough back to catch partial weeks
        while cur <= end_date:
            if cur.weekday() == 4:  # Friday
                triplet = []
                all_in_range = True
                for d in range(3):
                    date = cur + timedelta(days=d)
                    if not (start_date <= date <= end_date):
                        all_in_range = False
                        break
                    days_since = (date - start_date).days
                    w = days_since // 7
                    k = days_since % 7
                    triplet.append((w, k))
                # Only keep the triplet if **all three days** are in the schedule
                if all_in_range and len(triplet) == 3:
                    weekends.append(triplet)
            cur += timedelta(days=1)

        # Mark every scheduled shift (any area) for each employee
        worked = {e: [[0]*7 for _ in range(num_weeks)] for e in employees}
        for area in areas:
            sched = result_dict.get(f"{area.lower()}_schedule", [])
            for e, date_str, _, _, a in sched:
                if a != area or e not in employees:
                    continue
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue
                days_since = (date - start_date).days
                if 0 <= days_since < 7*num_weeks:
                    w = days_since // 7
                    k = days_since % 7
                    worked[e][w][k] = 1

        # Detect violations
        violations = []
        for e in employees:
            max_d = max_weekend_days.get(e, 2)
            for weekend in weekends:
                count = sum(worked[e][w][k] for w, k in weekend)
                if count > max_d:
                    # Build human-readable date range for this weekend
                    fri_date = start_date + timedelta(days=weekend[0][0]*7 + weekend[0][1])
                    sun_date = start_date + timedelta(days=weekend[2][0]*7 + weekend[2][1])
                    date_range = f"{fri_date:%b %d}–{sun_date:%b %d}, {fri_date.year}"
                    violations.append(
                        f"{e} has {count} weekend days (max {max_d}) on {date_range}"
                    )

    # -------------------------------------------------
    # 2. Compute required extra staff per area
    # -------------------------------------------------
    current_employees = {area: sum(1 for e in employees if area in work_areas[e]) for area in areas}
    required_employees = {area: current_employees[area] for area in areas}
    for v in violations:
        try:
            # "Joe C has 3 weekend days (max 1) on Nov 01–Nov 03, 2025"
            emp_name = v.split(" has ")[0]
            count_str = v.split(" has ")[1].split(" weekend")[0]
            count = int(count_str)
            max_d = max_weekend_days.get(emp_name, 2)
        except Exception:
            logging.warning(f"Could not parse violation string: {v}")
            continue
        excess = count - max_d
        if excess <= 0:
            continue
        # Employee works in exactly one area
        emp_area = next((a for a in work_areas[emp_name] if a in areas), None)
        if emp_area:
            required_employees[emp_area] += excess

    # -------------------------------------------------
    # 3. Build the human-readable summary
    # -------------------------------------------------
    lines = ["Employee Summary (Current vs Required):"]
    for area in areas:
        lines.append(f"- {area}: {current_employees[area]} current employees, "
                     f"{required_employees[area]} employees required to avoid weekend violations")
    summary = "\n".join(lines)
    return required_employees, summary, violations

def adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text):
    """
    Adjust column widths for Treeview widgets and summary text width based on window size.
    """
    width = root.winfo_width()
    for tree in all_listboxes:
        total_content_width = 0
        for col in tree["columns"]:
            max_width = max(len(col) * 10, 100)
            for item in tree.get_children():
                value = tree.set(item, col)
                max_width = max(max_width, len(str(value)) * 8)
            tree.column(col, width=max_width, minwidth=100, stretch=1)
            total_content_width += max_width
        tree_frame = tree.master
        hsb = tree_frame.children.get('!scrollbar2')
        if hsb and total_content_width > width - 50:
            hsb.grid()
        elif hsb:
            hsb.grid_remove()
    for tree in all_input_trees:
        total_content_width = 0
        for col in tree["columns"]:
            max_width = max(len(col) * 10, 100)
            for item in tree.get_children():
                value = tree.set(item, col)
                max_width = max(max_width, len(str(value)) * 8)
            tree.column(col, width=max_width, minwidth=100, stretch=1)
            total_content_width += max_width
        tree_frame = tree.master
        hsb = tree_frame.children.get('!scrollbar2')
        if hsb and total_content_width > width - 50:
            hsb.grid()
        elif hsb:
            hsb.grid_remove()
    notebook.update_idletasks()
    char_width = max(50, (width - 30) // 10)
    summary_text.configure(width=char_width)

def on_resize(event, root, all_listboxes, all_input_trees, notebook, summary_text):
    """
    Handle window resize event to adjust widget sizes.
    """
    if event.widget == root:
        adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)

def on_mousewheel(event, canvas):
    """
    Handle mouse wheel scrolling for the canvas.
    """
    canvas.yview_scroll(-1 * (event.delta // 120), "units")