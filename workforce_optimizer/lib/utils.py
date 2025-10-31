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

def min_employees_to_avoid_weekend_violations(max_weekend_days, areas, violations, work_areas, employees):
    """
    Calculate the minimum number of employees needed per area to avoid Max Number of Weekend Days violations,
    based on actual violations from validate_weekend_constraints.
    """
    # Initialize counts
    current_employees = {area: sum(1 for e in employees if area in work_areas[e]) for area in areas}
    required_employees = {area: current_employees[area] for area in areas}  # Start with current count

    # Parse violations to increment required employees
    for violation in violations:
        # Extract employee name (handle one or two parts)
        emp_name = violation.split(" has ")[0].strip()
        if emp_name not in employees:
            logging.warning(f"Employee {emp_name} from violation not found in employee list")
            continue
        
        # Extract assigned weekend days from violation (e.g., "has 3 weekend days")
        try:
            assigned_days = int(violation.split(" has ")[1].split(" weekend days")[0])
        except (IndexError, ValueError):
            logging.warning(f"Could not parse assigned days from violation: {violation}")
            continue

        # Get max weekend days for the employee
        max_days = max_weekend_days.get(emp_name, 2)  # Default to 2 if not found
        excess_days = assigned_days - max_days
        if excess_days <= 0:
            continue  # No excess, no additional employees needed

        # Add excess days to the required employees for the employee's work area
        emp_area = work_areas[emp_name][0]  # Assume single work area per employee
        required_employees[emp_area] += excess_days

    # Format the summary string
    summary = "Employee Summary (Current vs Required):\n"
    for area in areas:
        summary += f"- {area}: {current_employees[area]} current employees, {required_employees[area]} employees required to avoid weekend violations\n"
    
    return required_employees, summary

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