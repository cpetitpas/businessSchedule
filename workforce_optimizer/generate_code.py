# generate_code.py
import json
import hashlib
import base64
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import appdirs

APP_NAME = "Workforce Optimizer"
AUTHOR   = "Chris"

# CORRECT KEY DECODE
SECRET_KEY = base64.urlsafe_b64decode('LjPORB9ANrbEpCgGse3Ww-3v1gpsbeF0TV-blAc_1rk=')
FIXED_IV = b'WorkforceOpt1234'

dirs = appdirs.AppDirs(APP_NAME, appauthor=False)
TRIAL_FILE = Path(dirs.user_data_dir) / "data" / "trial.dat"

def main():
    print("\n" + "="*60)
    print("       REGISTRATION CODE GENERATOR")
    print("="*60 + "\n")

    if not TRIAL_FILE.exists():
        print("ERROR: trial.dat not found!")
        print("Run the main application first.")
        input("\nPress Enter to exit...")
        return

    try:
        with open(TRIAL_FILE, 'rb') as f:
            token = f.read()
        cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(FIXED_IV), backend=default_backend())
        decryptor = cipher.decryptor()
        plain_padded = decryptor.update(token) + decryptor.finalize()
        pad_len = plain_padded[-1]
        plain = plain_padded[:-pad_len]
        data = json.loads(plain.decode())
        start_date = data["start"]

        payload = f"{APP_NAME}|{AUTHOR}|{start_date}"
        digest = hashlib.sha256(payload.encode()).digest()
        code = base64.urlsafe_b64encode(digest).decode().rstrip("=")[:20]

        print(f"   REGISTRATION CODE:  {code}")
        print(f"\n   Start date: {start_date}")
        print("   This code is 100% STABLE.")
        print("="*60)
        input("\nPress Enter to close...")

    except Exception as e:
        print(f"ERROR: {e}")
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()