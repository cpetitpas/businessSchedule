import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from config import load_config, on_closing
from gui_handlers import generate_schedule, display_input_data, save_input_data, save_schedule_changes
from utils import adjust_column_widths, on_resize, on_mousewheel
from constants import DEFAULT_GEOMETRY
import logging
import matplotlib.pyplot as plt

# Configure logging with date and time in filename
from datetime import datetime
log_file = f"workforce_optimizer_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Tkinter GUI with scrollable canvas
root = tk.Tk()
root.title("Workforce Optimizer")
root.geometry(DEFAULT_GEOMETRY)

# Create canvas and scrollbar
canvas = tk.Canvas(root)
scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

# Configure canvas
canvas.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

# Update scroll region and canvas width when frame size changes
def on_frame_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))
    canvas.itemconfig(canvas_frame, width=event.width)

scrollable_frame.bind("<Configure>", on_frame_configure)
canvas.bind("<Configure>", on_frame_configure)

# Global variables
emp_file_var = tk.StringVar()
req_file_var = tk.StringVar()
limits_file_var = tk.StringVar()
start_date_entry = None
num_weeks_var = tk.IntVar(value=2)
all_listboxes = []
all_input_trees = []
bar_frame = None
kitchen_frame = None
emp_frame = None
req_frame = None
limits_frame = None
notebook = None
summary_text = None
viz_frame = None

# GUI setup
def setup_gui():
    global start_date_entry, bar_frame, kitchen_frame, emp_frame, req_frame, limits_frame, notebook, summary_text, viz_frame
    from tkcalendar import DateEntry
    # Start date selection
    tk.Label(scrollable_frame, text="Select Start Date:").pack(pady=5)
    start_date_entry = DateEntry(scrollable_frame, width=12, background='darkblue', foreground='white', borderwidth=2, year=2025, firstweekday='sunday', showweeknumbers=False)
    start_date_entry.pack(pady=5)

    # Number of weeks input
    tk.Label(scrollable_frame, text="Number of Weeks (1 or more):").pack(pady=5)
    num_weeks_entry = tk.Entry(scrollable_frame, textvariable=num_weeks_var, width=10)
    num_weeks_entry.pack(pady=5)

    # File selection for Employee Data
    tk.Label(scrollable_frame, text="Select Employee Data CSV:").pack(pady=5)
    emp_entry = tk.Entry(scrollable_frame, textvariable=emp_file_var, width=50)
    emp_entry.pack(pady=5)
    tk.Button(scrollable_frame, text="Browse", command=lambda: emp_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")]))).pack(pady=5)

    # File selection for Personnel Required
    tk.Label(scrollable_frame, text="Select Personnel Required CSV:").pack(pady=5)
    req_entry = tk.Entry(scrollable_frame, textvariable=req_file_var, width=50)
    req_entry.pack(pady=5)
    tk.Button(scrollable_frame, text="Browse", command=lambda: req_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")]))).pack(pady=5)

    # File selection for Hard Limits
    tk.Label(scrollable_frame, text="Select Hard Limits CSV:").pack(pady=5)
    limits_entry = tk.Entry(scrollable_frame, textvariable=limits_file_var, width=50)
    limits_entry.pack(pady=5)
    tk.Button(scrollable_frame, text="Browse", command=lambda: limits_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")]))).pack(pady=5)

    # View Input Data button
    tk.Button(scrollable_frame, text="View Input Data", command=lambda: display_input_data(emp_file_var.get(), req_file_var.get(), limits_file_var.get(), emp_frame, req_frame, limits_frame, root, notebook, summary_text)).pack(pady=5)

    # Save Input Data button
    tk.Button(scrollable_frame, text="Save Input Data", command=lambda: save_input_data(emp_file_var.get(), req_file_var.get(), limits_file_var.get(), emp_frame, req_frame, limits_frame)).pack(pady=5)

    # Input data tabs
    notebook = ttk.Notebook(scrollable_frame)
    notebook.pack(pady=10, fill="both", expand=True)
    scrollable_frame.columnconfigure(0, weight=1)

    # Employee Data tab
    emp_frame = tk.Frame(notebook)
    emp_frame.grid_rowconfigure(0, weight=1)
    emp_frame.grid_columnconfigure(0, weight=1)
    notebook.add(emp_frame, text="Employee Data")

    # Personnel Required tab
    req_frame = tk.Frame(notebook)
    req_frame.grid_rowconfigure(0, weight=1)
    req_frame.grid_columnconfigure(0, weight=1)
    notebook.add(req_frame, text="Personnel Required")

    # Hard Limits tab
    limits_frame = tk.Frame(notebook)
    limits_frame.grid_rowconfigure(0, weight=1)
    limits_frame.grid_columnconfigure(0, weight=1)
    notebook.add(limits_frame, text="Hard Limits")

    # Summary report tab
    summary_tab = tk.Frame(notebook)
    summary_tab.grid_rowconfigure(0, weight=1)
    summary_tab.grid_columnconfigure(0, weight=1)
    notebook.add(summary_tab, text="Summary Report")
    summary_frame = tk.Frame(summary_tab)
    summary_frame.grid(row=0, column=0, sticky="nsew")
    summary_tab.rowconfigure(0, weight=1)
    summary_tab.columnconfigure(0, weight=1)
    summary_text = tk.Text(summary_frame, wrap="none", height=10)
    summary_yscroll = ttk.Scrollbar(summary_frame, orient="vertical", command=summary_text.yview)
    summary_xscroll = ttk.Scrollbar(summary_frame, orient="horizontal", command=summary_text.xview)
    summary_text.configure(yscrollcommand=summary_yscroll.set, xscrollcommand=summary_xscroll.set)
    summary_text.grid(row=0, column=0, sticky="nsew")
    summary_yscroll.grid(row=0, column=1, sticky="ns")
    summary_xscroll.grid(row=1, column=0, sticky="ew")
    summary_frame.rowconfigure(0, weight=1)
    summary_frame.columnconfigure(0, weight=1)

    # Schedule display frames
    tk.Label(scrollable_frame, text="Bar Schedule").pack(pady=5)
    bar_frame = tk.Frame(scrollable_frame)
    bar_frame.pack(pady=5, fill="both", expand=True)

    tk.Label(scrollable_frame, text="Kitchen Schedule").pack(pady=5)
    kitchen_frame = tk.Frame(scrollable_frame)
    kitchen_frame.pack(pady=5, fill="both", expand=True)

    # Visualization frame
    tk.Label(scrollable_frame, text="Visualizations").pack(pady=5)
    viz_frame = tk.Frame(scrollable_frame)
    viz_frame.pack(pady=5, fill="both", expand=True)

    # Generate button
    tk.Button(scrollable_frame, text="Generate Schedule", command=lambda: generate_schedule(emp_file_var.get(), req_file_var.get(), limits_file_var.get(), start_date_entry, num_weeks_var, bar_frame, kitchen_frame, summary_text, viz_frame, root, notebook)).pack(pady=10)

    # Save Schedule Changes button
    tk.Button(scrollable_frame, text="Save Schedule Changes", command=lambda: save_schedule_changes(bar_frame, kitchen_frame, start_date_entry.get_date(), root)).pack(pady=10)

# Main execution
if __name__ == "__main__":
    setup_gui()
    load_config(root, emp_file_var, req_file_var, limits_file_var)
    root.bind("<Configure>", lambda event: on_resize(event, root, all_listboxes, all_input_trees, notebook, summary_text))
    root.bind("<MouseWheel>", lambda event: on_mousewheel(event, canvas))
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(emp_file_var, req_file_var, limits_file_var, root))
    root.update_idletasks()
    adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)
    logging.info("Application started")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
        on_closing(emp_file_var, req_file_var, limits_file_var, root)
        root.quit()