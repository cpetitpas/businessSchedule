import os
import sys
import shutil
import glob

# ---------------------------------------------------------------
# resource_path() — MUST BE DEFINED FIRST
# ---------------------------------------------------------------
def resource_path(relative_path):
    """Return absolute path to bundled file (works in dev & frozen)."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base, relative_path)

# ---------------------------------------------------------------
# Extract bundled data (called by installer)
# ---------------------------------------------------------------
def extract_bundled_data(target_dir: str):
    """Extract bundled data/*.csv → target_dir"""
    try:
        src = resource_path('data')
        if not os.path.isdir(src):
            return
        os.makedirs(target_dir, exist_ok=True)
        for src_file in glob.glob(os.path.join(src, '**', '*.csv'), recursive=True):
            rel = os.path.relpath(src_file, src)
            dst = os.path.join(target_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src_file, dst)
    except Exception as e:
        # Log to a temp file so installer doesn't crash
        import tempfile
        log_path = os.path.join(tempfile.gettempdir(), 'workforce_install_error.log')
        with open(log_path, 'w') as f:
            f.write(f"Extraction failed: {e}\n")
        # Do NOT raise — installer must continue

# ---------------------------------------------------------------
# Handle installer extraction request
# ---------------------------------------------------------------
if len(sys.argv) == 3 and sys.argv[1] == '--extract-data':
    extract_bundled_data(sys.argv[2])
    sys.exit(0)

# ---------------------------------------------------------------
# install_sample_data() — fallback for first run
# ---------------------------------------------------------------
def install_sample_data():
    from lib.utils import user_data_dir
    target = user_data_dir()
    src_dir = resource_path('data')
    try:
        if os.path.isdir(src_dir) and not os.listdir(target):
            for src in glob.glob(os.path.join(src_dir, '**', '*.csv'), recursive=True):
                rel = os.path.relpath(src, src_dir)
                dst = os.path.join(target, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
    except Exception:
        pass  # Silent fail — user can browse manually


import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from lib.config import load_config, on_closing
from lib.gui_handlers import generate_schedule, display_input_data, save_input_data, save_schedule_changes
from lib.utils import adjust_column_widths, on_resize, on_mousewheel, user_data_dir, user_log_dir, user_output_dir
from lib.data_loader import load_csv
from lib.constants import DEFAULT_GEOMETRY
import logging
import matplotlib.pyplot as plt

# Configure logging with date and time in filename
from datetime import datetime
log_file = os.path.join(user_log_dir(), f"workforce_optimizer_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Tkinter GUI with scrollable canvas
root = tk.Tk()
try:
    root.iconbitmap(resource_path(r'icons\teamwork.ico'))
except Exception as e:
    print(f"Could not load icon: {e}")
root.title("Workforce Optimizer")
root.geometry(DEFAULT_GEOMETRY)

# Hide the root window initially
#root.withdraw()

def show_disclaimer(parent):
    """
    Display a standard disclaimer/security statement when the application starts.
    """
    disclaimer_text = (
        "DISCLAIMER AND SECURITY STATEMENT\n\n"
        "This Workforce Optimizer application is provided 'as is' without any warranties, express or implied, "
        "including but not limited to warranties of merchantability, fitness for a particular purpose, or non-infringement. "
        "The developers and contributors are not responsible for any damages, losses, or liabilities arising from the use of this software, "
        "including but not limited to direct, indirect, incidental, or consequential damages.\n\n"
        "This software is licensed for use by the original recipient only and is non-transferable. "
        "All rights are reserved by the developers. Unauthorized distribution, modification, or commercial use is prohibited.\n\n"
        "For support or inquiries, contact chris070411@gmail.com.\n\n"
        "By using this application, you agree to these terms."
    )
    messagebox.showinfo("Disclaimer", disclaimer_text, parent=parent)
# ---- NEW: TRIAL DIALOG -------------------------------------------------
from lib.trial import TrialManager
import tkinter.messagebox as mb

def show_trial_dialog(parent):
    try:
        tm = TrialManager()
    except Exception as e:
        logging.error(f"Trial init failed: {e}", exc_info=True)
        messagebox.showerror("Trial Error", f"Cannot start trial system:\n{e}")
        parent.quit()
        return

    days = tm.days_left()
    dlg = tk.Toplevel(parent)
    dlg.title("Trial Status")
    dlg.geometry("460x280")
    dlg.transient(parent)
    dlg.grab_set()

    # centre
    dlg.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (dlg.winfo_width() // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (dlg.winfo_height() // 2)
    dlg.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    if tm.is_registered():
        msg = "This copy is **registered** – full version."
        show_register = False
        btn_text = "Continue"
        btn_cmd = dlg.destroy
    elif days == 0:
        msg = ("**TRIAL EXPIRED**\n"
               "Contact chris070411@gmail.com for a registration code.")
        show_register = True
        btn_text = "Exit"
        btn_cmd = lambda: parent.quit()          # <-- HARD EXIT
    else:
        msg = (f"**{days} day{'s' if days != 1 else ''} left** in your 30-day trial.\n"
               "Contact chris070411@gmail.com for a registration code.")
        show_register = True
        btn_text = "Continue"
        btn_cmd = dlg.destroy

    tk.Label(dlg, text=msg, justify="center", padx=20, pady=15, font=("Arial", 10)).pack()

    # ------------------------------------------------------------------
    if show_register:
        frm = tk.Frame(dlg)
        frm.pack(pady=8)
        entry = tk.Entry(frm, width=30, justify="center")
        entry.pack(side="left", padx=5)

        def do_register():
            ok, txt = tm.register(entry.get())
            messagebox.showinfo("Registration", txt)
            if ok:
                dlg.destroy()

        tk.Button(frm, text="Register", command=do_register).pack(side="left")

    # ------------------------------------------------------------------
    tk.Button(dlg, text=btn_text, command=btn_cmd).pack(pady=12)
    parent.wait_window(dlg)

# Show disclaimer before rendering the main window
show_disclaimer(root)
show_trial_dialog(root)

# Restore the root window after disclaimer is dismissed
#root.deiconify()

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
emp_frame = None
req_frame = None
limits_frame = None
notebook = None
summary_text = None
viz_frame = None
current_areas = []

# GUI setup
def setup_gui():
    global start_date_entry, scrollable_frame, emp_frame, req_frame, limits_frame, notebook, summary_text, viz_frame

    def generate_and_store_areas():
        """Generate schedule and store areas for saving."""
        global current_areas
        try:
            emp_path = emp_file_var.get()
            req_path = req_file_var.get()
            limits_path = limits_file_var.get()
            start_date = start_date_entry.get_date()
            num_weeks = num_weeks_var.get()

            if not all([emp_path, req_path, limits_path]):
                messagebox.showerror("Error", "Please select all input files.")
                return

            # === Call generate_schedule with the REAL frame ===
            generate_schedule(
                emp_path, req_path, limits_path,
                start_date_entry, num_weeks_var,
                None, None,  # bar_frame, kitchen_frame (deprecated)
                summary_text, viz_frame, root, notebook, schedule_container  # ← Real frame
            )

            # === Re-run load_csv to get areas ===
            result = load_csv(emp_path, req_path, limits_path, start_date, num_weeks)
            if result is not None:
                _, _, _, areas, _, _, _, _, _, _, _, _, _ = result
                current_areas = areas
                logging.info(f"Stored areas: {current_areas}")
            else:
                current_areas = []

        except Exception as e:
            messagebox.showerror("Error", f"Generation failed: {e}")
            logging.error(f"generate_and_store_areas error: {e}")
            current_areas = []
    from tkcalendar import DateEntry

    # Company logo section
    logo_frame = tk.Frame(scrollable_frame)
    logo_frame.pack(pady=10)

    try:
        # Load and display company logo
        from PIL import Image, ImageTk
        logo_path = resource_path(os.path.join('images', 'silver-spur-logo-shadowed.png'))  # Place your logo file in the same directory
        logo_image = Image.open(logo_path)
        # Resize logo if needed (adjust width/height as desired)
        logo_image = logo_image.resize((200, 100), Image.Resampling.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_image)
        logo_label = tk.Label(logo_frame, image=logo_photo)
        logo_label.image = logo_photo  # Keep a reference to prevent garbage collection
        logo_label.pack()
    except (FileNotFoundError, ImportError) as e:
        # Fallback if logo file not found or PIL not available
        tk.Label(logo_frame, text="Company Logo", font=("Arial", 12, "bold"), 
                fg="blue", relief="ridge", padx=20, pady=10).pack()
        
    # Start date selection
    tk.Label(scrollable_frame, text="Select Start Date:").pack(pady=5)
    start_date_entry = DateEntry(scrollable_frame, width=12, background='darkblue', foreground='white', borderwidth=2, year=2025, firstweekday='sunday', showweeknumbers=False)
    start_date_entry.pack(pady=5)

    # Number of weeks input
    tk.Label(scrollable_frame, text="Number of Weeks (1 or more):").pack(pady=5)
    num_weeks_entry = tk.Entry(scrollable_frame, textvariable=num_weeks_var, width=10)
    num_weeks_entry.pack(pady=5)

    # File selection section - organized in a single row
    file_selection_frame = tk.Frame(scrollable_frame)
    file_selection_frame.pack(pady=10, fill="x")
    
    # Employee Data column
    emp_column = tk.Frame(file_selection_frame)
    emp_column.pack(side="left", fill="x", expand=True, padx=5)
    tk.Label(emp_column, text="Employee Data CSV:").pack()
    emp_entry = tk.Entry(emp_column, textvariable=emp_file_var, width=25)
    emp_entry.pack(pady=2)
    tk.Button(emp_column, text="Browse", command=lambda: emp_file_var.set(filedialog.askopenfilename(initialdir=user_data_dir(), filetypes=[("CSV files", "*.csv")]) or emp_file_var.get())).pack(pady=2)
    
    # Personnel Required column
    req_column = tk.Frame(file_selection_frame)
    req_column.pack(side="left", fill="x", expand=True, padx=5)
    tk.Label(req_column, text="Personnel Required CSV:").pack()
    req_entry = tk.Entry(req_column, textvariable=req_file_var, width=25)
    req_entry.pack(pady=2)
    tk.Button(req_column, text="Browse", command=lambda: req_file_var.set(filedialog.askopenfilename(initialdir=user_data_dir(), filetypes=[("CSV files", "*.csv")]) or req_file_var.get())).pack(pady=2)
    
    # Hard Limits column
    limits_column = tk.Frame(file_selection_frame)
    limits_column.pack(side="left", fill="x", expand=True, padx=5)
    tk.Label(limits_column, text="Hard Limits CSV:").pack()
    limits_entry = tk.Entry(limits_column, textvariable=limits_file_var, width=25)
    limits_entry.pack(pady=2)
    tk.Button(limits_column, text="Browse", command=lambda: limits_file_var.set(filedialog.askopenfilename(initialdir=user_data_dir(), filetypes=[("CSV files", "*.csv")]) or limits_file_var.get())).pack(pady=2)

    # View Input Data button
    tk.Button(scrollable_frame, text="View Input Data", command=lambda: display_input_data(emp_file_var.get(), req_file_var.get(), limits_file_var.get(), emp_frame, req_frame, limits_frame, root, notebook, summary_text)).pack(pady=5)

    # Save Input Data button
    tk.Button(scrollable_frame, text="Save Input Data", command=lambda: save_input_data(emp_file_var.get(), req_file_var.get(), limits_file_var.get(), emp_frame, req_frame, limits_frame, root)).pack(pady=5)

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

    # Generate button
    tk.Button(scrollable_frame, text="Generate Schedule", 
          command=lambda: generate_and_store_areas()).pack(pady=10)

    # Save Schedule Changes button
    tk.Button(scrollable_frame, text="Save Schedule Changes", 
          command=lambda: save_schedule_changes(
              start_date_entry.get_date(),
              root,
              schedule_container,  # ← Pass the real Frame
              current_areas
          )).pack(pady=10)

    # === SCHEDULES SECTION ===
    tk.Label(scrollable_frame, text="Schedules", font=("Arial", 12, "bold")).pack(pady=(20, 5), anchor="center")

    # ← CREATE THE ACTUAL FRAME
    schedule_container = tk.Frame(scrollable_frame)
    schedule_container.pack(pady=5, fill="both", expand=True)

    # Visualization frame (existing)
    tk.Label(scrollable_frame, text="Visualizations", font=("Arial", 12, "bold")).pack(pady=5)
    viz_frame = tk.Frame(scrollable_frame)
    viz_frame.pack(pady=5, fill="both", expand=True)

# Main execution
if __name__ == "__main__":
    # 1. Extract sample data on first run (fallback if installer failed)
    install_sample_data()

    # 2. Normal GUI startup
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