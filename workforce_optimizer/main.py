# main.py
import os
import sys
import shutil
import glob

TRIAL_PASSED = False

# ---------------------------------------------------------------
# resource_path()
# ---------------------------------------------------------------
def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base, relative_path)

# ---------------------------------------------------------------
# install_sample_data()
# ---------------------------------------------------------------
def install_sample_data():
    from lib.utils import user_data_dir
    target_dir = user_data_dir()
    src_dir = resource_path('data')  # Now works in onedir

    try:
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # SKIP IF ANY CSV EXISTS
        if any(f.lower().endswith('.csv') for f in os.listdir(target_dir)):
            logging.info("Sample data already exists — skipping copy")
            return

        logging.info("Copying sample data...")
        for src in glob.glob(os.path.join(src_dir, '**', '*.csv'), recursive=True):
            rel = os.path.relpath(src, src_dir)
            dst = os.path.join(target_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        logging.info("Sample data copied successfully")
    except Exception as e:
        logging.error(f"Failed to copy sample data: {e}")

# ---------------------------------------------------------------
# CRITICAL: CHECK TRIAL BEFORE ANY TKINTER
# ---------------------------------------------------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from lib.config import load_config, on_closing
from lib.gui_handlers import generate_schedule, display_input_data, save_input_data, save_schedule_changes
from lib.utils import adjust_column_widths, on_resize, on_mousewheel, user_data_dir, user_log_dir, user_output_dir
from lib.data_loader import load_csv
from lib.constants import DEFAULT_GEOMETRY
import logging
from datetime import datetime
from lib.trial import TrialManager

# Setup logging FIRST
log_file = os.path.join(user_log_dir(), f"workforce_optimizer_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def check_trial_and_exit():
    try:
        tm = TrialManager()
        if tm.is_registered():
            return True
        days = tm.days_left()
        if days == 0:
            root = tk.Tk()
            root.withdraw()
            try:
                root.iconbitmap(resource_path(r'icons\teamwork.ico'))
            except:
                pass

            msg = (
                "TRIAL EXPIRED\n\n"
                "Your 30-day trial has ended.\n"
                "To continue using Workforce Optimizer,\n"
                "please purchase a license.\n\n"
                "Contact: chris070411@gmail.com"
            )
            messagebox.showwarning("Trial Expired", msg, parent=root)
            root.destroy()
            logging.warning("Trial expired – user blocked")
            return False
        else:
            return True
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Trial system error:\n{e}")
        root.destroy()
        logging.error(f"Trial init failed: {e}", exc_info=True)
        return False

# === IN if __name__ == "__main__": ===
if not check_trial_and_exit():
    sys.exit(0)

# ---------------------------------------------------------------
# MAIN: TRIAL CHECK FIRST
# ---------------------------------------------------------------
if __name__ == "__main__":
    # BLOCK GUI IF TRIAL FAILS
    if not check_trial_and_exit():
        sys.exit(0)

    # ONLY NOW: START TKINTER
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    
    root = tk.Tk()
    root.title("Workforce Optimizer")
    root.geometry("1200x800")
    try:
        root.iconbitmap(resource_path(r'icons\teamwork.ico'))
    except Exception as e:
        print(f"Icon error: {e}")

    # ------------------------------------------------------------------
    # MODAL DIALOGS (run BEFORE any GUI widgets)
    # ------------------------------------------------------------------
    def show_disclaimer(parent):
        text = (
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
        messagebox.showinfo("Disclaimer", text, parent=parent)

    # ---- TRIAL DIALOG -------------------------------------------------
    from lib.trial import TrialManager
    import tkinter.messagebox as mb

    def show_trial_dialog(parent):
        global TRIAL_PASSED  # ← CRITICAL

        try:
            tm = TrialManager()
        except Exception as e:
            logging.error(f"Trial init failed: {e}", exc_info=True)
            mb.showerror("Trial Error", f"Cannot start trial system:\n{e}")
            sys.exit(1)

        days = tm.days_left()
        dlg = tk.Toplevel(parent)
        dlg.title("Trial Status")
        dlg.geometry("460x280")
        dlg.transient(parent)
        dlg.grab_set()

        # Center
        dlg.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (dlg.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (dlg.winfo_height() // 2)
        dlg.geometry(f"+{x}+{y}")

        # Disable X on expired
        if days == 0:
            dlg.protocol("WM_DELETE_WINDOW", lambda: None)
        else:
            dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

        if tm.is_registered():
            msg = "This copy is **registered** – full version."
            show_register = False
            btn_text = "Continue"
            btn_cmd = lambda: [setattr(parent, 'TRIAL_PASSED', True), dlg.destroy()]
        elif days == 0:
            msg = ("**TRIAL EXPIRED**\n"
                   "Contact chris070411@gmail.com for a registration code.")
            show_register = True
            btn_text = "Exit"
            btn_cmd = lambda: [parent.quit(), sys.exit(0)]
        else:
            msg = (f"**{days} day{'s' if days != 1 else ''} left** in your 30-day trial.\n"
                   "Contact chris070411@gmail.com for a registration code.")
            show_register = True
            btn_text = "Continue"
            btn_cmd = lambda: [setattr(parent, 'TRIAL_PASSED', True), dlg.destroy()]

        tk.Label(dlg, text=msg, justify="center", padx=20, pady=15, font=("Arial", 10)).pack()

        if show_register:
            frm = tk.Frame(dlg)
            frm.pack(pady=8)
            entry = tk.Entry(frm, width=30, justify="center")
            entry.pack(side="left", padx=5)

            def do_register():
                ok, txt = tm.register(entry.get())
                mb.showinfo("Registration", txt)
                if ok:
                    parent.TRIAL_PASSED = True
                    dlg.destroy()

            tk.Button(frm, text="Register", command=do_register).pack(side="left")

        tk.Button(dlg, text=btn_text, command=btn_cmd).pack(pady=12)
        parent.wait_window(dlg)

    # === SHOW DIALOGS ===
    show_disclaimer(root)
    root.TRIAL_PASSED = False  # ← Attach to root
    show_trial_dialog(root)

    if not root.TRIAL_PASSED:
        logging.info("Trial expired or not passed — exiting")
        root.quit()
        sys.exit(0)

    install_sample_data()

    # ------------------------------------------------------------------
    # GUI BUILD (only if we get here)
    # ------------------------------------------------------------------
    canvas = tk.Canvas(root)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(canvas_frame, width=event.width)

    scrollable_frame.bind("<Configure>", on_frame_configure)
    canvas.bind("<Configure>", on_frame_configure)

    # Globals
    emp_file_var = tk.StringVar()
    req_file_var = tk.StringVar()
    limits_file_var = tk.StringVar()
    start_date_entry = None
    num_weeks_var = tk.IntVar(value=2)
    all_listboxes = []
    all_input_trees = []
    emp_frame = req_frame = limits_frame = None
    notebook = summary_text = viz_frame = None
    current_areas = []

    def setup_gui():
        global start_date_entry, emp_frame, req_frame, limits_frame, notebook, summary_text, viz_frame

        def generate_and_store_areas():
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
                generate_schedule(
                    emp_path, req_path, limits_path,
                    start_date_entry, num_weeks_var,
                    None, None,
                    summary_text, viz_frame, root, notebook, schedule_container
                )
                result = load_csv(emp_path, req_path, limits_path, start_date, num_weeks)
                if result:
                    _, _, _, areas, *_ = result
                    current_areas = areas
            except Exception as e:
                messagebox.showerror("Error", f"Generation failed: {e}")
                logging.error(f"generate_and_store_areas error: {e}")

        from tkcalendar import DateEntry

        # === LOGO ===
        logo_frame = tk.Frame(scrollable_frame)
        logo_frame.pack(pady=10)
        try:
            from PIL import Image, ImageTk
            logo_path = resource_path(os.path.join('images', 'silver-spur-logo-shadowed.png'))
            img = Image.open(logo_path).resize((200, 100), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(logo_frame, image=photo)
            lbl.image = photo  # Keep reference
            lbl.pack()
        except Exception:
            tk.Label(logo_frame, text="Company Logo", font=("Arial", 12, "bold"), fg="blue", relief="ridge", padx=20, pady=10).pack()

        # === DATE & WEEKS ===
        tk.Label(scrollable_frame, text="Select Start Date:").pack(pady=5)
        start_date_entry = DateEntry(scrollable_frame, width=12, background='darkblue', foreground='white', borderwidth=2, year=2025, firstweekday='sunday')
        start_date_entry.pack(pady=5)
        tk.Label(scrollable_frame, text="Number of Weeks (1 or more):").pack(pady=5)
        tk.Entry(scrollable_frame, textvariable=num_weeks_var, width=10).pack(pady=5)

        # === FILE SELECTION ===
        file_frame = tk.Frame(scrollable_frame)
        file_frame.pack(pady=10, fill="x")
        for label, var in [("Employee Data CSV:", emp_file_var), ("Personnel Required CSV:", req_file_var), ("Hard Limits CSV:", limits_file_var)]:
            col = tk.Frame(file_frame)
            col.pack(side="left", fill="x", expand=True, padx=5)
            tk.Label(col, text=label).pack()
            tk.Entry(col, textvariable=var, width=25).pack(pady=2)
            tk.Button(col, text="Browse", command=lambda v=var: v.set(
                filedialog.askopenfilename(initialdir=user_data_dir(), filetypes=[("CSV files", "*.csv")]) or v.get()
            )).pack(pady=2)

        # === NOTEBOOK + FRAMES (CRITICAL: BEFORE BUTTONS) ===
        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(pady=10, fill="both", expand=True)

        # Employee Data
        emp_frame = tk.Frame(notebook)
        emp_frame.grid(row=0, column=0, sticky="nsew")
        emp_frame.grid_rowconfigure(0, weight=1)
        emp_frame.grid_columnconfigure(0, weight=1)
        notebook.add(emp_frame, text="Employee Data")
        globals()['emp_frame'] = emp_frame  # ← CRITICAL

        # Personnel Required
        req_frame = tk.Frame(notebook)
        req_frame.grid(row=0, column=0, sticky="nsew")
        req_frame.grid_rowconfigure(0, weight=1)
        req_frame.grid_columnconfigure(0, weight=1)
        notebook.add(req_frame, text="Personnel Required")
        globals()['req_frame'] = req_frame  # ← CRITICAL

        # Hard Limits
        limits_frame = tk.Frame(notebook)
        limits_frame.grid(row=0, column=0, sticky="nsew")
        limits_frame.grid_rowconfigure(0, weight=1)
        limits_frame.grid_columnconfigure(0, weight=1)
        notebook.add(limits_frame, text="Hard Limits")
        globals()['limits_frame'] = limits_frame  # ← CRITICAL

        # === SUMMARY TAB ===
        summary_tab = tk.Frame(notebook)
        summary_tab.grid_rowconfigure(0, weight=1)
        summary_tab.grid_columnconfigure(0, weight=1)
        notebook.add(summary_tab, text="Summary Report")
        sframe = tk.Frame(summary_tab)
        sframe.grid(row=0, column=0, sticky="nsew")
        summary_tab.rowconfigure(0, weight=1)
        summary_tab.columnconfigure(0, weight=1)
        summary_text = tk.Text(sframe, wrap="none", height=10)
        sy = ttk.Scrollbar(sframe, orient="vertical", command=summary_text.yview)
        sx = ttk.Scrollbar(sframe, orient="horizontal", command=summary_text.xview)
        summary_text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        summary_text.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        sframe.rowconfigure(0, weight=1)
        sframe.columnconfigure(0, weight=1)

        # === BUTTONS (NOW SAFE) ===
        tk.Button(scrollable_frame, text="View Input Data", command=lambda: display_input_data(
            emp_file_var.get(), req_file_var.get(), limits_file_var.get(),
            emp_frame, req_frame, limits_frame, root, notebook, summary_text
        )).pack(pady=5)

        tk.Button(scrollable_frame, text="Save Input Data", command=lambda: save_input_data(
            emp_file_var.get(), req_file_var.get(), limits_file_var.get(),
            emp_frame, req_frame, limits_frame, root
        )).pack(pady=5)

        # === GENERATE & SAVE ===
        tk.Button(scrollable_frame, text="Generate Schedule", command=generate_and_store_areas).pack(pady=10)
        tk.Button(scrollable_frame, text="Save Schedule Changes", command=lambda: save_schedule_changes(
            start_date_entry.get_date(), root, schedule_container, current_areas
        )).pack(pady=10)

        # === SCHEDULES ===
        tk.Label(scrollable_frame, text="Schedules", font=("Arial", 12, "bold")).pack(pady=(20, 5), anchor="center")
        schedule_container = tk.Frame(scrollable_frame)
        schedule_container.pack(pady=5, fill="both", expand=True)

        # === VISUALIZATIONS ===
        tk.Label(scrollable_frame, text="Visualizations", font=("Arial", 12, "bold")).pack(pady=5)
        viz_frame = tk.Frame(scrollable_frame)
        viz_frame.pack(pady=5, fill="both", expand=True)

    # ------------------------------------------------------------------
    # FINAL SETUP
    # ------------------------------------------------------------------
    setup_gui()
    load_config(root, emp_file_var, req_file_var, limits_file_var)
    root.bind("<Configure>", lambda e: on_resize(e, root, all_listboxes, all_input_trees, notebook, summary_text))
    root.bind("<MouseWheel>", lambda e: on_mousewheel(e, canvas))
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(emp_file_var, req_file_var, limits_file_var, root))
    root.update_idletasks()
    adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)
    logging.info("Application started")

    # === START EVENT LOOP ===
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Application terminated")