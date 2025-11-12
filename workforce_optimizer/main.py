# main.py
import os
import sys
import shutil
import glob
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from lib.utils import show_settings_dialog

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

def open_user_guide():
    """Open the local user guide (PDF or HTML) using system default viewer."""
    doc_path = resource_path(os.path.join('docs', 'UserGuide.pdf'))
    try:
        # Convert to file:// URL for cross-platform safety
        url = Path(doc_path).as_uri()
        webbrowser.open(url)
    except Exception as e:
        messagebox.showerror("Help Error", f"Could not open documentation:\n{e}")

# ---------------------------------------------------------------
# install_sample_data() – lazy copy, only if missing
# ---------------------------------------------------------------
def install_sample_data():
    try:
        import appdirs
        from pathlib import Path
        from lib.utils import user_data_dir, _load_settings

        src_dir = resource_path('data')

        # Compute the true default directory (exactly what user_data_dir() returns when no custom is set)
        default_dir = str(Path(appdirs.user_data_dir(appname='Workforce Optimizer', appauthor=False)) / "data")

        target_dir = user_data_dir()

        settings = _load_settings()

        # If "data_dir" key exists (even if value == default_dir), user has explicitly set/changed it → never copy again
        if "data_dir" in settings:
            return

        if target_dir != default_dir:
            return

        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        if any(f.lower().endswith('.csv') for f in os.listdir(target_dir)):
                return

        logging.info("Fresh install detected – copying sample data")

        for src in glob.glob(os.path.join(src_dir, '**', '*.csv'), recursive=True):
                rel = os.path.relpath(src, src_dir)
                dst = os.path.join(target_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                logging.debug(f"Copied sample: {rel}")

    except Exception as e:
        logging.error(f"install_sample_data failed: {e}")
        pass  # Silent fail – user sees missing data later

# ---------------------------------------------------------------
# check_trial_and_exit() – fast, minimal UI
# ---------------------------------------------------------------
def check_trial_and_exit():
    try:
        from lib.trial import TrialManager
        tm = TrialManager()

        # === EARLY EXIT LOGIC: Block if expired (trial OR license) ===
        days = tm.days_left()  

        if days == 0:
            root = tk.Tk()
            root.withdraw()
            try:
                root.iconbitmap(resource_path(r'icons\teamwork.ico'))
            except:
                pass
            msg = (
                "LICENSE EXPIRED\n\n"
                "Your 30-day trial or 1-year license has ended.\n"
                "To continue using Workforce Optimizer,\n"
                "please purchase a new license.\n\n"
                "Contact: chris070411@gmail.com"
            )
            messagebox.showwarning("License Expired", msg, parent=root)
            root.destroy()
            return False  
        return True  

    except Exception as e:
        logging.error(f"check_trial_and_exit failed: {e}", exc_info=True)
        return True  # Never block startup

# ---------------------------------------------------------------
# MAIN: Fast splash + deferred heavy work
# ---------------------------------------------------------------
if __name__ == "__main__":
    if not check_trial_and_exit():
        sys.exit(0)

    # ------------------------------------------------------------------
    # 1. Create the hidden root window (no geometry yet)
    # ------------------------------------------------------------------
    root = tk.Tk()
    root.withdraw()                     # keep it off-screen for now
    root.title("Workforce Optimizer")
    try:
        root.iconbitmap(resource_path(r'icons\teamwork.ico'))
    except:
        pass

    # ------------------------------------------------------------------
    # 2. Add the **Settings** menu **before** the splash
    # ------------------------------------------------------------------
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    # ---- File menu ----------------------------------------------------
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(
        label="Exit",
        command=lambda: on_closing(emp_file_var, req_file_var, limits_file_var, root)
    )

    # ---- Settings menu ------------------------------------------------
    settings_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Settings", menu=settings_menu)
    settings_menu.add_command(
        label="Folder Locations…",
        command=lambda: show_settings_dialog(root)   # from lib.utils
    )

    # ---- Help menu ----------------------------------------------------
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(
        label="User Guide",
        command=open_user_guide
)

    # ------------------------------------------------------------------
    # 3. Ultra-fast splash (shown while the heavy UI is built)
    # ------------------------------------------------------------------
    splash = tk.Toplevel(root)
    splash.title("Loading...")
    splash.geometry("400x200")
    splash.resizable(False, False)
    splash.overrideredirect(True)
    splash.configure(bg="#f8f9fa")

    splash.update_idletasks()
    x = (splash.winfo_screenwidth() // 2) - (splash.winfo_width() // 2)
    y = (splash.winfo_screenheight() // 2) - (splash.winfo_height() // 2)
    splash.geometry(f"+{x}+{y}")

    tk.Label(splash, text="Workforce Optimizer", font=("Arial", 16, "bold"),
             bg="#f8f9fa", fg="#212529").pack(pady=25)
    tk.Label(splash, text="Initializing application...", font=("Arial", 10),
             bg="#f8f9fa", fg="#495057").pack(pady=5)
    progress = ttk.Progressbar(splash, mode='indeterminate', length=300)
    progress.pack(pady=20, padx=40)
    progress.start()
    root.update()                       # force splash to appear immediately

    # ------------------------------------------------------------------
    # 4. DEFERRED heavy work (logging, sample data, UI build)
    # ------------------------------------------------------------------
    # ---- logging ----------------------------------------------------
    from lib.utils import user_log_dir
    from datetime import datetime
    import logging
    from logging.handlers import RotatingFileHandler

    log_dir = user_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir,
                            f"workforce_optimizer_{datetime.now():%Y-%m-%d_%H-%M-%S}.log")

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000,
                                       backupCount=5, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    logging.debug("Logging system initialized")
    logging.info("Application startup")

    # ---- copy sample data (only on fresh install) -------------------
    install_sample_data()

    # ---- build the *full* GUI (still hidden) ------------------------
    # (All the code that was previously under “NOW BUILD GUI”)
    root.geometry("1200x800")
    root.minsize(1000, 600)

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

    # Globals (same as before)
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
                from lib.gui_handlers import generate_schedule
                generate_schedule(
                    emp_file_var, req_file_var, limits_file_var,
                    start_date_entry, num_weeks_var,
                    summary_text, viz_frame, root, notebook, schedule_container,
                    emp_frame, req_frame, limits_frame
                )
                from lib.data_loader import load_csv
                result = load_csv(emp_path, req_path, limits_path, start_date, num_weeks)
                if result:
                    _, _, _, areas, *_ = result
                    current_areas = areas
            except Exception as e:
                messagebox.showerror("Error", f"Generation failed: {e}")
                logging.error(f"generate_and_store_areas error: {e}")

        # === LAZY IMPORTS ===
        from tkcalendar import DateEntry
        try:
            from PIL import Image, ImageTk
            logo_path = resource_path(os.path.join('images', 'silver-spur-logo-shadowed.png'))
            img = Image.open(logo_path).resize((200, 100), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            logo_frame = tk.Frame(scrollable_frame)
            logo_frame.pack(pady=10)
            lbl = tk.Label(logo_frame, image=photo)
            lbl.image = photo
            lbl.pack()
        except Exception:
            tk.Label(scrollable_frame, text="Company Logo", font=("Arial", 12, "bold"), fg="blue", relief="ridge", padx=20, pady=10).pack()

        # === DATE & WEEKS ===
        date_weeks_frame = tk.Frame(scrollable_frame)
        date_weeks_frame.pack(pady=10)
        
        # Left side: Date
        date_col = tk.Frame(date_weeks_frame)
        date_col.pack(side="left", padx=20)
        tk.Label(date_col, text="Select Start Date:").pack()
        start_date_entry = DateEntry(date_col, width=12, background='darkblue', foreground='white', borderwidth=2, year=2025, firstweekday='sunday')
        start_date_entry.pack(pady=5)
        
        # Right side: Weeks
        weeks_col = tk.Frame(date_weeks_frame)
        weeks_col.pack(side="left", padx=20)
        tk.Label(weeks_col, text="Number of Weeks (1 or more):").pack()
        tk.Entry(weeks_col, textvariable=num_weeks_var, width=10).pack(pady=5)

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

        # === NOTEBOOK + FRAMES ===
        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(pady=10, fill="both", expand=True)

        emp_frame = tk.Frame(notebook)
        emp_frame.grid(row=0, column=0, sticky="nsew")
        emp_frame.grid_rowconfigure(0, weight=1)
        emp_frame.grid_columnconfigure(0, weight=1)
        notebook.add(emp_frame, text="Employee Data")
        globals()['emp_frame'] = emp_frame

        req_frame = tk.Frame(notebook)
        req_frame.grid(row=0, column=0, sticky="nsew")
        req_frame.grid_rowconfigure(0, weight=1)
        req_frame.grid_columnconfigure(0, weight=1)
        notebook.add(req_frame, text="Personnel Required")
        globals()['req_frame'] = req_frame

        limits_frame = tk.Frame(notebook)
        limits_frame.grid(row=0, column=0, sticky="nsew")
        limits_frame.grid_rowconfigure(0, weight=1)
        limits_frame.grid_columnconfigure(0, weight=1)
        notebook.add(limits_frame, text="Hard Limits")
        globals()['limits_frame'] = limits_frame

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

        # === BUTTONS ===
        from lib.gui_handlers import display_input_data, save_input_data, save_schedule_changes

        # First row: View and Save Input Data buttons
        btn_row1 = tk.Frame(scrollable_frame)
        btn_row1.pack(pady=5)
        tk.Button(btn_row1, text="View Input Data", command=lambda: display_input_data(
            emp_file_var.get(), req_file_var.get(), limits_file_var.get(),
            emp_frame, req_frame, limits_frame, root, notebook, summary_text
        )).pack(side="left", padx=5)
        tk.Button(btn_row1, text="Save Input Data", command=lambda: save_input_data(
            emp_file_var, req_file_var, limits_file_var,
            emp_frame, req_frame, limits_frame, root
        )).pack(side="left", padx=5)
        
        # Second row: Generate Schedule and Save Schedule Changes buttons
        btn_row2 = tk.Frame(scrollable_frame)
        btn_row2.pack(pady=5)
        tk.Button(btn_row2, text="Generate Schedule", command=generate_and_store_areas).pack(side="left", padx=5)
        tk.Button(btn_row2, text="Save Schedule Changes", command=lambda: save_schedule_changes(
            start_date_entry.get_date(), root, schedule_container, current_areas
        )).pack(side="left", padx=5)

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
    # ------------------------------------------------------------------
    # 4. Close splash and **show** the fully-built window
    # ------------------------------------------------------------------
    splash.destroy()
    root.deiconify()                     # now the UI appears

    # ------------------------------------------------------------------
    # 5. Restore saved geometry (or centre on first run)
    # ------------------------------------------------------------------
    from lib.config import load_config
    config = load_config(root, emp_file_var, req_file_var, limits_file_var)
    if config is None:
        config = {}
    if config.get("window_geometry"):
        try:
            root.geometry(config["window_geometry"])
        except Exception:
            pass
    else:
        # centre the main window when there is no saved geometry
        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (w // 2)
        y = (root.winfo_screenheight() // 2) - (h // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # 6. Modal dialogs (Disclaimer → Trial)
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

    def show_trial_dialog(parent):
        global TRIAL_PASSED

        dlg = tk.Toplevel(parent)
        dlg.title("License Status")
        dlg.geometry("460x280")
        dlg.transient(parent)
        dlg.grab_set()

        try:
            dlg.iconbitmap(resource_path(r'icons\teamwork.ico'))
        except:
            pass

        dlg.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (dlg.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (dlg.winfo_height() // 2)
        dlg.geometry(f"+{x}+{y}")

        try:
            from lib.trial import TrialManager
            tm = TrialManager()
            days = tm.days_left()

            if days == 0:
                # EXPIRED — NO CONTINUE
                msg = ("**LICENSE EXPIRED**\n\n"
                    "Your 30-day trial or 1-year license has ended.\n"
                    "To continue using Workforce Optimizer,\n"
                    "please purchase a new license.\n\n"
                    "Contact: chris070411@gmail.com")
                show_register = True
                btn_text = "Exit"
                btn_cmd = lambda: [parent.quit(), sys.exit(0)]
                dlg.protocol("WM_DELETE_WINDOW", lambda: None)
            elif tm.is_registered():
                msg = (f"**{days} day{'s' if days != 1 else ''} left** in your 1-year license.\n"
                    "Contact chris070411@gmail.com for renewal.")
                show_register = False
                btn_text = "Continue"
                btn_cmd = lambda: [setattr(parent, 'TRIAL_PASSED', True), dlg.destroy()]
            else:
                msg = (f"**{days} day{'s' if days != 1 else ''} left** in your 30-day trial.\n"
                    "Contact chris070411@gmail.com for a registration code.")
                show_register = True
                btn_text = "Continue"
                btn_cmd = lambda: [setattr(parent, 'TRIAL_PASSED', True), dlg.destroy()]

        except Exception as e:
            logging.error(f"Trial system error: {e}", exc_info=True)
            msg = f"License error:\n{e}"
            show_register = False
            btn_text = "Exit"
            btn_cmd = lambda: [parent.quit(), sys.exit(0)]

        tk.Label(dlg, text=msg, justify="center", padx=20, pady=15, font=("Arial", 10)).pack()

        if show_register:
            frm = tk.Frame(dlg)
            frm.pack(pady=8)
            entry = tk.Entry(frm, width=30, justify="center")
            entry.pack(side="left", padx=5)

            def do_register():
                try:
                    from lib.trial import TrialManager
                    tm2 = TrialManager()
                    ok, txt = tm2.register(entry.get())
                    messagebox.showinfo("Registration", txt)
                    if ok:
                        parent.TRIAL_PASSED = True
                        dlg.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Registration failed:\n{e}")

            tk.Button(frm, text="Register", command=do_register).pack(side="left")

        tk.Button(dlg, text=btn_text, command=btn_cmd).pack(pady=12)
        parent.wait_window(dlg)

    show_disclaimer(root)
    show_trial_dialog(root)

    # ------------------------------------------------------------------
    # 7. Final UI wiring (bindings, column widths, etc.)
    # ------------------------------------------------------------------
    from lib.utils import adjust_column_widths, on_resize, on_mousewheel, user_data_dir
    from lib.config import on_closing

    root.bind("<Configure>", lambda e: on_resize(e, root, all_listboxes,
                                               all_input_trees, notebook, summary_text))
    root.bind("<MouseWheel>", lambda e: on_mousewheel(e, canvas))
    root.protocol("WM_DELETE_WINDOW",
                  lambda: on_closing(emp_file_var, req_file_var, limits_file_var, root))

    root.update_idletasks()
    adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)
    logging.info("Application started")

    # ------------------------------------------------------------------
    # 8. Event loop
    # ------------------------------------------------------------------
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Application terminated")