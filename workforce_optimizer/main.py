# main.py
import os
import sys
import shutil
import glob
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

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
# install_sample_data() – lazy copy
# ---------------------------------------------------------------
def install_sample_data():
    try:
        from lib.utils import user_data_dir
        target_dir = user_data_dir()
        src_dir = resource_path('data')

        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        if any(f.lower().endswith('.csv') for f in os.listdir(target_dir)):
            return

        for src in glob.glob(os.path.join(src_dir, '**', '*.csv'), recursive=True):
            rel = os.path.relpath(src, src_dir)
            dst = os.path.join(target_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    except Exception:
        pass

# ---------------------------------------------------------------
# check_trial_and_exit() – ultra fast
# ---------------------------------------------------------------
def check_trial_and_exit():
    try:
        from lib.trial import TrialManager
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
            messagebox.showwarning("Trial Expired",
                "TRIAL EXPIRED\n\nYour 30-day trial has ended.\n"
                "To continue using Workforce Optimizer,\nplease purchase a license.\n\n"
                "Contact: chris070411@gmail.com", parent=root)
            root.destroy()
            return False
        return True
    except Exception:
        return True

# ---------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------
if __name__ == "__main__":
    if not check_trial_and_exit():
        sys.exit(0)

    # ================= ULTRA-FAST SPLASH =================
    root = tk.Tk()
    root.withdraw()
    root.title("Workforce Optimizer")
    try:
        root.iconbitmap(resource_path(r'icons\teamwork.ico'))
    except:
        pass

    splash = tk.Toplevel(root)
    splash.title("Loading...")
    splash.geometry("420x220")
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
    progress = ttk.Progressbar(splash, mode='indeterminate', length=320)
    progress.pack(pady=25, padx=40)
    progress.start(10)

    root.update()

    # ================= DEFERRED HEAVY WORK =================
    from lib.utils import user_log_dir
    from datetime import datetime
    import logging
    from logging.handlers import RotatingFileHandler

    log_dir = user_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"workforce_optimizer_{datetime.now():%Y-%m-%d_%H-%M-%S}.log")

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)
    logging.info("Application startup - splash shown")

    install_sample_data()

    # --- MODAL DIALOGS (still under splash) ---
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
        try:
            from lib.trial import TrialManager
            tm = TrialManager()
        except Exception as e:
            logging.error(f"Trial init failed: {e}", exc_info=True)
            messagebox.showerror("Trial Error", f"Cannot start trial system:\n{e}")
            sys.exit(1)

        days = tm.days_left()
        dlg = tk.Toplevel(parent)
        dlg.title("Trial Status")
        dlg.geometry("460x280")
        dlg.transient(parent)
        dlg.grab_set()
        try:
            dlg.iconbitmap(resource_path(r'icons\teamwork.ico'))
        except:
            pass

        dlg.update_idletasks()
        # Position trial dialog below splash screen
        splash_y = splash.winfo_y()
        splash_height = splash.winfo_height()
        x = (dlg.winfo_screenwidth() // 2) - (dlg.winfo_width() // 2)
        y = splash_y + splash_height + 20  # 20px gap below splash
        dlg.geometry(f"+{x}+{y}")

        if days == 0:
            dlg.protocol("WM_DELETE_WINDOW", lambda: None)

        if tm.is_registered():
            msg = "This copy is **registered** – full version."
            show_register = False
            btn_text = "Continue"
            btn_cmd = lambda: [setattr(parent, 'TRIAL_PASSED', True), dlg.destroy()]
        elif days == 0:
            msg = "**TRIAL EXPIRED**\nContact chris070411@gmail.com for a registration code."
            show_register = True
            btn_text = "Exit"
            btn_cmd = lambda: sys.exit(0)
        else:
            msg = f"**{days} day{'s' if days != 1 else ''} left** in your 30-day trial.\nContact chris070411@gmail.com for a registration code."
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
                messagebox.showinfo("Registration", txt)
                if ok:
                    parent.TRIAL_PASSED = True
                    dlg.destroy()
            tk.Button(frm, text="Register", command=do_register).pack(side="left")
        tk.Button(dlg, text=btn_text, command=btn_cmd).pack(pady=12)
        parent.wait_window(dlg)

    show_disclaimer(root)
    root.TRIAL_PASSED = False
    show_trial_dialog(root)
    if not root.TRIAL_PASSED:
        splash.destroy()
        logging.info("Trial not passed — exiting")
        sys.exit(0)

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
    schedule_container = None

     # === LOAD CONFIG FIRST (includes geometry + file paths) ===
    from lib.config import load_config, on_closing
    from lib.utils import adjust_column_widths, on_resize, on_mousewheel, user_data_dir, show_settings_dialog
    load_config(root, emp_file_var, req_file_var, limits_file_var)  # NOW RESTORES GEOMETRY

    root.deiconify()
    root.minsize(1000, 600)

    # === NOW BUILD GUI WITH CORRECT SIZE ===
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

    def setup_gui():
        global start_date_entry, emp_frame, req_frame, limits_frame, notebook, summary_text, viz_frame, schedule_container

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
                    emp_file_var.get(), req_file_var.get(), limits_file_var.get(),
                    start_date_entry, num_weeks_var,
                    None, None,
                    summary_text, viz_frame, root, notebook, schedule_container,
                    emp_file_var, req_file_var, limits_file_var
                )
                from lib.data_loader import load_csv
                result = load_csv(emp_path, req_path, limits_path, start_date, num_weeks)
                if result:
                    _, _, _, areas, *_ = result
                    current_areas = areas
            except Exception as e:
                messagebox.showerror("Error", f"Generation failed: {e}")
                logging.error(f"generate_and_store_areas error: {e}")

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

        tk.Label(scrollable_frame, text="Select Start Date:").pack(pady=5)
        start_date_entry = DateEntry(scrollable_frame, width=12, background='darkblue', foreground='white', borderwidth=2, year=2025, firstweekday='sunday')
        start_date_entry.pack(pady=5)
        tk.Label(scrollable_frame, text="Number of Weeks (1 or more):").pack(pady=5)
        tk.Entry(scrollable_frame, textvariable=num_weeks_var, width=10).pack(pady=5)

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

        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(pady=10, fill="both", expand=True)

        emp_frame = tk.Frame(notebook); notebook.add(emp_frame, text="Employee Data"); globals()['emp_frame'] = emp_frame
        req_frame = tk.Frame(notebook); notebook.add(req_frame, text="Personnel Required"); globals()['req_frame'] = req_frame
        limits_frame = tk.Frame(notebook); notebook.add(limits_frame, text="Hard Limits"); globals()['limits_frame'] = limits_frame

        summary_tab = tk.Frame(notebook); notebook.add(summary_tab, text="Summary Report")
        sframe = tk.Frame(summary_tab); sframe.pack(fill="both", expand=True)
        summary_text = tk.Text(sframe, wrap="none")
        sy = ttk.Scrollbar(sframe, orient="vertical", command=summary_text.yview)
        sx = ttk.Scrollbar(sframe, orient="horizontal", command=summary_text.xview)
        summary_text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        summary_text.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")

        from lib.gui_handlers import display_input_data, save_input_data, save_schedule_changes
        tk.Button(scrollable_frame, text="View Input Data", command=lambda: display_input_data(
            emp_file_var.get(), req_file_var.get(), limits_file_var.get(),
            emp_frame, req_frame, limits_frame, root, notebook, summary_text
        )).pack(pady=5)
        tk.Button(scrollable_frame, text="Save Input Data", command=lambda: save_input_data(
            emp_file_var.get(), req_file_var.get(), limits_file_var.get(),
            emp_frame, req_frame, limits_frame, root,
            emp_file_var, req_file_var, limits_file_var
        )).pack(pady=5)
        tk.Button(scrollable_frame, text="Generate Schedule", command=generate_and_store_areas).pack(pady=10)
        tk.Button(scrollable_frame, text="Save Schedule Changes", command=lambda: save_schedule_changes(
            start_date_entry.get_date(), root, schedule_container, current_areas
        )).pack(pady=10)

        tk.Label(scrollable_frame, text="Schedules", font=("Arial", 12, "bold")).pack(pady=(20,5), anchor="center")
        schedule_container = tk.Frame(scrollable_frame)
        schedule_container.pack(pady=5, fill="both", expand=True)

        tk.Label(scrollable_frame, text="Visualizations", font=("Arial", 12, "bold")).pack(pady=5)
        viz_frame = tk.Frame(scrollable_frame)
        viz_frame.pack(pady=5, fill="both", expand=True)

    setup_gui()

    # MENU BAR
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Exit", command=lambda: on_closing(emp_file_var, req_file_var, limits_file_var, root))

    settings_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Settings", menu=settings_menu)
    settings_menu.add_command(label="Folder Locations…", command=lambda: show_settings_dialog(root))

    root.bind("<Configure>", lambda e: on_resize(e, root, all_listboxes, all_input_trees, notebook, summary_text))
    root.bind("<MouseWheel>", lambda e: on_mousewheel(e, canvas))
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(emp_file_var, req_file_var, limits_file_var, root))
    root.update_idletasks()
    adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)
    logging.info("GUI ready - hiding splash")
    splash.destroy()

    logging.info("Application started")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Application terminated")