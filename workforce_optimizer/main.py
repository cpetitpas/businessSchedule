import tkinter as tk
from tkinter import ttk
from config import load_config, save_config, on_closing
from gui_handlers import generate_schedule, display_input_data
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
all_trees = []
bar_frame = None
kitchen_frame = None
emp_text = None
req_text = None
limits_text = None
notebook = None

# GUI setup
def setup_gui():
    global start_date_entry, bar_frame, kitchen_frame, emp_text, req_text, limits_text, notebook
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

    # File selection for Personel Required
    tk.Label(scrollable_frame, text="Select Personel Required CSV:").pack(pady=5)
    req_entry = tk.Entry(scrollable_frame, textvariable=req_file_var, width=50)
    req_entry.pack(pady=5)
    tk.Button(scrollable_frame, text="Browse", command=lambda: [req_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config(emp_file_var, req_file_var, limits_file_var, root)]).pack(pady=5)

    # File selection for Hard Limits
    tk.Label(scrollable_frame, text="Select Hard Limits CSV:").pack(pady=5)
    limits_entry = tk.Entry(scrollable_frame, textvariable=limits_file_var, width=50)
    limits_entry.pack(pady=5)
    tk.Button(scrollable_frame, text="Browse", command=lambda: [limits_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config(emp_file_var, req_file_var, limits_file_var, root)]).pack(pady=5)

    # View Input Data button
    tk.Button(scrollable_frame, text="View Input Data", command=lambda: display_input_data(emp_file_var, req_file_var, limits_file_var, emp_text, req_text, limits_text, notebook)).pack(pady=5)

    # Input data tabs
    notebook = ttk.Notebook(scrollable_frame)
    notebook.pack(pady=10, fill="both", expand=True)

    # Employee Data tab
    emp_tab = tk.Frame(notebook)
    notebook.add(emp_tab, text="Employee Data")
    emp_text = tk.Text(emp_tab, wrap="none", height=10)
    emp_yscroll = ttk.Scrollbar(emp_tab, orient="vertical", command=emp_text.yview)
    emp_xscroll = ttk.Scrollbar(emp_tab, orient="horizontal", command=emp_text.xview)
    emp_text.configure(yscrollcommand=emp_yscroll.set, xscrollcommand=emp_xscroll.set)
    emp_xscroll.pack(side="bottom", fill="x")
    emp_yscroll.pack(side="right", fill="y")
    emp_text.pack(side="left", fill="both", expand=True)

    # Personel Required tab
    req_tab = tk.Frame(notebook)
    notebook.add(req_tab, text="Personel Required")
    req_text = tk.Text(req_tab, wrap="none", height=10)
    req_yscroll = ttk.Scrollbar(req_tab, orient="vertical", command=req_text.yview)
    req_xscroll = ttk.Scrollbar(req_tab, orient="horizontal", command=req_text.xview)
    req_text.configure(yscrollcommand=req_yscroll.set, xscrollcommand=req_xscroll.set)
    req_xscroll.pack(side="bottom", fill="x")
    req_yscroll.pack(side="right", fill="y")
    req_text.pack(side="left", fill="both", expand=True)

    # Hard Limits tab
    limits_tab = tk.Frame(notebook)
    notebook.add(limits_tab, text="Hard Limits")
    limits_text = tk.Text(limits_tab, wrap="none", height=10)
    limits_yscroll = ttk.Scrollbar(limits_tab, orient="vertical", command=limits_text.yview)
    limits_xscroll = ttk.Scrollbar(limits_tab, orient="horizontal", command=limits_text.xview)
    limits_text.configure(yscrollcommand=limits_yscroll.set, xscrollcommand=limits_xscroll.set)
    limits_xscroll.pack(side="bottom", fill="x")
    limits_yscroll.pack(side="right", fill="y")
    limits_text.pack(side="left", fill="both", expand=True)

    # Schedule display frames
    tk.Label(scrollable_frame, text="Bar Schedule").pack(pady=5)
    bar_frame = tk.Frame(scrollable_frame)
    bar_frame.pack(pady=5, fill="x")

    tk.Label(scrollable_frame, text="Kitchen Schedule").pack(pady=5)
    kitchen_frame = tk.Frame(scrollable_frame)
    kitchen_frame.pack(pady=5, fill="x")

    # Generate button
    tk.Button(scrollable_frame, text="Generate Schedule", command=lambda: generate_schedule(emp_file_var, req_file_var, limits_file_var, start_date_entry, num_weeks_var, bar_frame, kitchen_frame, all_trees)).pack(pady=10)

# Main execution
if __name__ == "__main__":
    from tkinter import filedialog
    setup_gui()
    load_config(root, emp_file_var, req_file_var, limits_file_var)
    root.bind("<Configure>", lambda event: on_resize(event, root, all_trees, notebook, emp_text, req_text, limits_text))
    root.bind("<MouseWheel>", lambda event: on_mousewheel(event, canvas))
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(emp_file_var, req_file_var, limits_file_var, root))
    root.update_idletasks()
    adjust_column_widths(root, all_trees, notebook, emp_text, req_text, limits_text)
    logging.info("Application started")
    root.mainloop()