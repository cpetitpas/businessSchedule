import math
from datetime import datetime, timedelta
import logging
import tkinter as tk
from tkinter import ttk
from constants import DAYS, SHIFTS

def min_employees_to_avoid_weekend_violations(required, max_weekend_days, areas, num_weeks):
    """
    Calculate the minimum number of employees needed per area to avoid Max Number of Weekend Days violations,
    assuming each employee can work up to the maximum allowed weekend days observed in the data.
    """
    max_possible = max(max_weekend_days.values()) if max_weekend_days else 2
    fri_sun_windows = []
    for w in range(num_weeks - 1):
        fri_sun_windows.append([(w, "Fri"), (w, "Sat"), (w + 1, "Sun")])
    if num_weeks > 0:
        fri_sun_windows.append([(num_weeks - 1, "Fri"), (num_weeks - 1, "Sat")])
    
    min_per_area = {}
    for area in areas:
        min_n = 0
        for window in fri_sun_windows:
            total_shifts = 0
            for w, d in window:
                for s in SHIFTS:
                    total_shifts += required[d][area][s]
            min_for_window = math.ceil(total_shifts / max_possible)
            min_n = max(min_n, min_for_window)
        min_per_area[area] = min_n
    return min_per_area

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