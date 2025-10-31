import math
import os
import appdirs
from datetime import datetime, timedelta
import logging
import tkinter as tk
from tkinter import ttk

def user_data_dir() -> str:
    """
    Returns:  %LOCALAPPDATA%\Workforce Optimizer\data
    """
    path = os.path.join(appdirs.user_data_dir(appname='Workforce Optimizer', appauthor=False), 'data')
    os.makedirs(path, exist_ok=True)
    return path

def user_log_dir() -> str:
    """
    Returns:  %LOCALAPPDATA%\Workforce Optimizer\logs
    """
    path = os.path.join(appdirs.user_data_dir(appname='Workforce Optimizer', appauthor=False), 'logs')
    os.makedirs(path, exist_ok=True)
    return path

def user_output_dir() -> str:
    """
    Returns:  %LOCALAPPDATA%\Workforce Optimizer\output
    """
    path = os.path.join(appdirs.user_data_dir(appname='Workforce Optimizer', appauthor=False), 'output')
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
        required_employees (dict area → int)
        summary_text (str)
        violations (list of str)   # now always populated
    """
    # -------------------------------------------------
    # 1. If we have a solved schedule → build violations from it
    # -------------------------------------------------
    if not violations and result_dict and start_date and num_weeks:
        end_date = start_date + timedelta(days=7 * num_weeks - 1)
        # Build a list of all weekend triplets (Fri-Sat-Sun) that fall inside the schedule
        weekends = []                     # each entry = [(week, day_idx), …] for Fri-Sat-Sun
        cur = start_date - timedelta(days=6)
        while cur <= end_date + timedelta(days=2):
            if cur.weekday() == 4:        # Friday
                triplet = []
                for d in range(3):
                    date = cur + timedelta(days=d)
                    if start_date <= date <= end_date:
                        days_since = (date - start_date).days
                        w = days_since // 7
                        k = days_since % 7
                        triplet.append((w, k))
                if triplet:
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
                    violations.append(f"{e} has {count} weekend days (max {max_d})")
    # -------------------------------------------------
    # 2. Compute required extra staff per area
    # -------------------------------------------------
    current_employees = {area: sum(1 for e in employees if area in work_areas[e]) for area in areas}
    required_employees = {area: current_employees[area] for area in areas}
    for v in violations:
        # v ≈ "Joe C has 3 weekend days (max 1)"
        try:
            emp_name = v.split(" has ")[0]
            count = int(v.split(" has ")[1].split(" weekend")[0])
            max_d = max_weekend_days.get(emp_name, 2)
        except Exception:
            logging.warning(f"Could not parse violation string: {v}")
            continue
        excess = count - max_d
        if excess <= 0:
            continue
        # Employee works in exactly one area (per the CSV layout)
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