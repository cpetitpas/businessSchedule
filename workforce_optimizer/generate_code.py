# generate_code.py — UI TO SELECT trial.dat
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import hashlib
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import appdirs

APP_NAME = "Workforce Optimizer"
AUTHOR   = "Chris"
SECRET_KEY = base64.urlsafe_b64decode('LjPORB9ANrbEpCgGse3Ww-3v1gpsbeF0TV-blAc_1rk=')
FIXED_IV = b'WorkforceOpt1234'

def decrypt_trial_dat(file_path):
    try:
        with open(file_path, 'rb') as f:
            token = f.read()
        cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(FIXED_IV), backend=default_backend())
        decryptor = cipher.decryptor()
        plain_padded = decryptor.update(token) + decryptor.finalize()
        pad_len = plain_padded[-1]
        plain = plain_padded[:-pad_len]
        return json.loads(plain.decode()), None
    except Exception as e:
        return None, str(e)

def generate_code():
    file_path = filedialog.askopenfilename(
        title="Select trial.dat file",
        filetypes=[("trial.dat", "trial.dat"), ("All files", "*.*")],
        initialdir=appdirs.user_data_dir(APP_NAME)
    )
    if not file_path:
        return

    data, error = decrypt_trial_dat(file_path)
    if error or not data:
        messagebox.showerror("Error", f"Failed to read trial.dat:\n{error}")
        return

    start = data["start"]
    payload = f"{APP_NAME}|{AUTHOR}|{start}"
    code = base64.urlsafe_b64encode(hashlib.sha256(payload.encode()).digest()).decode().rstrip("=")[:20]

    result = (
        f"REGISTRATION CODE\n"
        f"{'='*50}\n"
        f"   CODE: {code}\n"
        f"   Trial Start: {start}\n"
        f"{'='*50}\n\n"
        f"Send this code to the user."
    )

    result_win = tk.Toplevel()
    result_win.title("Registration Code")
    result_win.geometry("500x300")
    result_win.resizable(False, False)

    tk.Label(result_win, text="SUCCESS!", font=("Arial", 14, "bold"), fg="green").pack(pady=10)
    text = tk.Text(result_win, wrap="word", font=("Consolas", 10))
    text.pack(padx=20, pady=10, fill="both", expand=True)
    text.insert("1.0", result)
    text.config(state="disabled")

    tk.Button(result_win, text="Copy to Clipboard", command=lambda: result_win.clipboard_clear() or result_win.clipboard_append(code)).pack(pady=5)
    tk.Button(result_win, text="Close", command=result_win.destroy).pack(pady=5)

# === GUI ===
root = tk.Tk()
root.title("Registration Code Generator")
root.geometry("400x200")
root.resizable(False, False)

tk.Label(root, text="Workforce Optimizer", font=("Arial", 16, "bold")).pack(pady=20)
tk.Label(root, text="Select trial.dat to generate registration code").pack(pady=10)
tk.Button(root, text="Choose trial.dat", command=generate_code, width=20, height=2).pack(pady=10)

root.mainloop()