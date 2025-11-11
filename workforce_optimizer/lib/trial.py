# trial.py
import os
import json
import base64
import hashlib
from datetime import datetime
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import appdirs
import logging
import winreg

APP_NAME = "Workforce Optimizer"
AUTHOR   = "Chris"
TRIAL_DAYS = 30

# 32-byte key (decoded from base64)
SECRET_KEY = base64.urlsafe_b64decode('LjPORB9ANrbEpCgGse3Ww-3v1gpsbeF0TV-blAc_1rk=')
FIXED_IV = b'WorkforceOpt1234'  # 16 bytes

TEST_OVERRIDE_DAYS_LEFT = None  # Set to 0 to test expiry

dirs = appdirs.AppDirs(APP_NAME, appauthor=False)
TRIAL_FILE = Path(dirs.user_data_dir) / "data" / "trial.dat"
BACKUP_FILE = Path(dirs.user_data_dir) / "cache" / "sys.dat"
REG_PATH = r"SOFTWARE\WorkforceOptimizer"
REG_NAME = "TrialData"

class TrialManager:
    def __init__(self):
        os.makedirs(dirs.user_data_dir + "/data", exist_ok=True)
        os.makedirs(dirs.user_data_dir + "/cache", exist_ok=True)
        self.data = self._load_from_any_source()
        self._sync_all_sources()

    def _encrypt(self, data):
        payload = json.dumps(data).encode()
        pad_len = 16 - (len(payload) % 16)
        payload += bytes([pad_len]) * pad_len
        cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(FIXED_IV), backend=default_backend())
        encryptor = cipher.encryptor()
        return encryptor.update(payload) + encryptor.finalize()

    def _decrypt(self, token):
        try:
            cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(FIXED_IV), backend=default_backend())
            decryptor = cipher.decryptor()
            plain_padded = decryptor.update(token) + decryptor.finalize()
            pad_len = plain_padded[-1]
            plain = plain_padded[:-pad_len]
            return json.loads(plain.decode())
        except:
            return None

    def _load_from_file(self, path):
        if path.exists():
            try:
                return self._decrypt(path.read_bytes())
            except:
                return None
        return None

    def _load_from_registry(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, REG_NAME)
            winreg.CloseKey(key)
            return self._decrypt(base64.b64decode(value))
        except:
            return None

    def _load_from_any_source(self):
        data = (
            self._load_from_file(TRIAL_FILE) or
            self._load_from_file(BACKUP_FILE) or
            self._load_from_registry()
        )
        if not data:
            data = {"start": datetime.now().date().isoformat(), "registered": False}
            logging.info("New trial created")
        return data

    def _save_to_file(self, path, data):
        try:
            path.write_bytes(self._encrypt(data))
        except:
            pass

    def _save_to_registry(self, data):
        try:
            encrypted = base64.b64encode(self._encrypt(data)).decode()
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
            winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, encrypted)
            winreg.CloseKey(key)
        except:
            pass

    def _sync_all_sources(self):
        self._save_to_file(TRIAL_FILE, self.data)
        self._save_to_file(BACKUP_FILE, self.data)
        self._save_to_registry(self.data)

    def is_registered(self) -> bool:
        return self.data.get("registered", False)

    def days_left(self) -> int:
        if self.is_registered():
            return 999
        if TEST_OVERRIDE_DAYS_LEFT is not None:
            return max(0, TEST_OVERRIDE_DAYS_LEFT)
        start = datetime.fromisoformat(self.data["start"]).date()
        elapsed = (datetime.now().date() - start).days
        return max(0, TRIAL_DAYS - elapsed)

    def register(self, code: str) -> tuple[bool, str]:
        expected = self._make_code()
        if code.strip() == expected:
            self.data["registered"] = True
            self._sync_all_sources()
            return True, "Registration successful!"
        return False, "Invalid code."

    def _make_code(self) -> str:
        payload = f"{APP_NAME}|{AUTHOR}|{self.data['start']}"
        digest = hashlib.sha256(payload.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:20]