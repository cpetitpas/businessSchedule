# config.py
import json
import os
import logging
import tkinter as tk
from tkinter import messagebox
import matplotlib.pyplot as plt
import threading

def load_config(root, emp_file_var, req_file_var, limits_file_var):
    logging.debug("Entering load_config")
    config_file = "config.json"
    default_geometry = "1000x600"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                emp_file_var.set(config.get("emp_file", ""))
                req_file_var.set(config.get("req_file", ""))
                limits_file_var.set(config.get("limits_file", ""))
                geometry = config.get("window_geometry", default_geometry)
                root.geometry(geometry)
                logging.info("Loaded config.json: %s", config)
        except Exception as e:
            logging.warning("Failed to load config.json: %s", str(e))
            root.geometry(default_geometry)
    else:
        logging.warning("config.json not found, using empty paths and default geometry")
        root.geometry(default_geometry)
    logging.debug("Exiting load_config")

def save_config(emp_file_var, req_file_var, limits_file_var, root):
    logging.debug("Entering save_config")
    config = {
        "emp_file": emp_file_var.get(),
        "req_file": req_file_var.get(),
        "limits_file": limits_file_var.get(),
        "window_geometry": root.geometry()
    }
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        logging.info("Saved config.json: %s", config)
    except Exception as e:
        logging.warning("Failed to save config.json: %s", str(e))
    logging.debug("Exiting save_config")

def on_closing(emp_file_var, req_file_var, limits_file_var, root):
    logging.debug("Starting application shutdown")
    try:
        save_config(emp_file_var, req_file_var, limits_file_var, root)
        plt.close('all')
        active_threads = [t for t in threading.enumerate() if t is not threading.main_thread()]
        if active_threads:
            logging.warning(f"Active threads detected during shutdown: {[t.name for t in active_threads]}")
        root.destroy()
        logging.info("Application closed successfully")
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")
        messagebox.showerror("Error", f"Failed to close application cleanly: {e}")
        root.destroy()  
    finally:
        root.quit()
        logging.debug("Exiting on_closing")