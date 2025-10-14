import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from config import load_config, save_config, on_closing
from gui_handlers import generate_schedule, display_input_data, parse_table_text_to_csv
from utils import adjust_column_widths, on_resize, on_mousewheel
from constants import DEFAULT_GEOMETRY
import logging

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
canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=root.winfo_width())

# Update scroll region and canvas width when frame size changes
def on_frame_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))
    canvas.itemconfig(canvas_frame, width=root.winfo_width())

scrollable_frame.bind("<Configure>", on_frame_configure)

# Global variables
emp_file_var = tk.StringVar()
req_file_var = tk.StringVar()
limits_file_var = tk.StringVar()
start_date_entry = None
num_weeks_var = tk.IntVar(value=2)
all_listboxes = []
all_input_trees = []  # For Treeviews
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
    tk.Button(scrollable_frame, text="Browse", command=lambda: [emp_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config(emp_file_var, req_file_var, limits_file_var, root)]).pack(pady=5)

    # File selection for Personnel Required
    tk.Label(scrollable_frame, text="Select Personnel Required CSV:").pack(pady=5)
    req_entry = tk.Entry(scrollable_frame, textvariable=req_file_var, width=50)
    req_entry.pack(pady=5)
    tk.Button(scrollable_frame, text="Browse", command=lambda: [req_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config(emp_file_var, req_file_var, limits_file_var, root)]).pack(pady=5)

    # File selection for Hard Limits
    tk.Label(scrollable_frame, text="Select Hard Limits CSV:").pack(pady=5)
    limits_entry = tk.Entry(scrollable_frame, textvariable=limits_file_var, width=50)
    limits_entry.pack(pady=5)
    tk.Button(scrollable_frame, text="Browse", command=lambda: [limits_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config(emp_file_var, req_file_var, limits_file_var, root)]).pack(pady=5)

    # View Input Data button
    tk.Button(scrollable_frame, text="View Input Data", command=lambda: display_input_data(emp_file_var.get(), req_file_var.get(), limits_file_var.get(), emp_frame, req_frame, limits_frame)).pack(pady=5)

    # Save Changes button
    tk.Button(scrollable_frame, text="Save Changes", command=lambda: parse_table_text_to_csv(emp_file_var.get(), req_file_var.get(), limits_file_var.get(), emp_frame, req_frame, limits_frame)).pack(pady=5)

    # Input data tabs
    notebook = ttk.Notebook(scrollable_frame)
    notebook.pack(pady=10, fill="both", expand=True)

    # Employee Data tab
    emp_frame = tk.Frame(notebook)
    notebook.add(emp_frame, text="Employee Data")

    # Personnel Required tab
    req_frame = tk.Frame(notebook)
    notebook.add(req_frame, text="Personnel Required")

    # Hard Limits tab
    limits_frame = tk.Frame(notebook)
    notebook.add(limits_frame, text="Hard Limits")

    # Summary report tab
    summary_tab = tk.Frame(notebook)
    notebook.add(summary_tab, text="Summary Report")
    summary_text = tk.Text(summary_tab, wrap="none", height=10)
    summary_yscroll = ttk.Scrollbar(summary_tab, orient="vertical", command=summary_text.yview)
    summary_xscroll = ttk.Scrollbar(summary_tab, orient="horizontal", command=summary_text.xview)
    summary_text.configure(yscrollcommand=summary_yscroll.set, xscrollcommand=summary_xscroll.set)
    summary_xscroll.pack(side="bottom", fill="x")
    summary_yscroll.pack(side="right", fill="y")
    summary_text.pack(side="left", fill="both", expand=True)

    # Schedule display frames
    tk.Label(scrollable_frame, text="Bar Schedule").pack(pady=5)
    bar_frame = tk.Frame(scrollable_frame)
    bar_frame.pack(pady=5, fill="x")

    tk.Label(scrollable_frame, text="Kitchen Schedule").pack(pady=5)
    kitchen_frame = tk.Frame(scrollable_frame)
    kitchen_frame.pack(pady=5, fill="x")

    # Visualization frame
    tk.Label(scrollable_frame, text="Visualizations").pack(pady=5)
    viz_frame = tk.Frame(scrollable_frame)
    viz_frame.pack(pady=5, fill="both", expand=True)

    # Generate button
    tk.Button(scrollable_frame, text="Generate Schedule", command=lambda: generate_schedule(emp_file_var, req_file_var, limits_file_var, start_date_entry, num_weeks_var, bar_frame, kitchen_frame, all_listboxes, summary_text, viz_frame, emp_frame, req_frame, limits_frame)).pack(pady=10)

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
    root.mainloop()