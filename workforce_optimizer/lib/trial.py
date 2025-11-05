# lib/trial.py
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

APP_NAME = "Workforce Optimizer"
AUTHOR   = "Chris"
TRIAL_DAYS = 30

# CORRECT: DECODE BASE64 TO 32 BYTES
SECRET_KEY = base64.urlsafe_b64decode('LjPORB9ANrbEpCgGse3Ww-3v1gpsbeF0TV-blAc_1rk=')
FIXED_IV = b'WorkforceOpt1234'  # 16 bytes

TEST_OVERRIDE_DAYS_LEFT = None

dirs = appdirs.AppDirs(APP_NAME, appauthor=False)
TRIAL_FILE = Path(dirs.user_data_dir) / "data" / "trial.dat"

class TrialManager:
    def __init__(self):
        os.makedirs(dirs.user_data_dir + "/data", exist_ok=True)
        self.data = self._load_or_create()
        logging.debug(f"Trial file: {TRIAL_FILE}")

    def _load_or_create(self):
        if TRIAL_FILE.exists():
            try:
                with open(TRIAL_FILE, 'rb') as f:
                    token = f.read()
                cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(FIXED_IV), backend=default_backend())
                decryptor = cipher.decryptor()
                plain_padded = decryptor.update(token) + decryptor.finalize()
                # Remove PKCS7 padding
                pad_len = plain_padded[-1]
                plain = plain_padded[:-pad_len]
                return json.loads(plain.decode())
            except Exception as e:
                logging.error(f"Corrupt trial.dat – recreating: {e}")
                TRIAL_FILE.unlink(missing_ok=True)

        start = datetime.now().date().isoformat()
        data = {"start": start, "registered": False}
        self._save(data)
        logging.info(f"Created trial.dat – start: {start}")
        return data

    def _save(self, data):
        payload = json.dumps(data).encode()
        # PKCS7 padding
        pad_len = 16 - (len(payload) % 16)
        payload += bytes([pad_len]) * pad_len
        cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(FIXED_IV), backend=default_backend())
        encryptor = cipher.encryptor()
        token = encryptor.update(payload) + encryptor.finalize()
        TRIAL_FILE.write_bytes(token)

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
            self._save(self.data)
            return True, "Registration successful!"
        return False, "Invalid code."

    def _make_code(self) -> str:
        payload = f"{APP_NAME}|{AUTHOR}|{self.data['start']}"
        digest = hashlib.sha256(payload.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:20]