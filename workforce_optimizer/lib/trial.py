# lib/trial.py
import os
import json
import base64
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet
import appdirs
import logging

# ----------------------------------------------------------------------
APP_NAME = "Workforce Optimizer"
AUTHOR   = "Christopher Petitpas"
TRIAL_DAYS = 30

# ----------------------------------------------------------------------
# 32-byte base64-encoded key (44 chars, ends with = if needed)
# ----------------------------------------------------------------------
SECRET_KEY = b'LjPORB9ANrbEpCgGse3Ww-3v1gpsbeF0TV-blAc_1rk='   # <-- replace with yours

# For quick testing only
TEST_OVERRIDE_DAYS_LEFT = None   # set to 0, 1, 5 … to force a value
# ----------------------------------------------------------------------

dirs = appdirs.AppDirs(APP_NAME, appauthor=False)
TRIAL_FILE = Path(dirs.user_data_dir) / "data" / "trial.dat"


class TrialManager:
    def __init__(self):
        self.cipher = Fernet(SECRET_KEY)
        os.makedirs(dirs.user_data_dir + "/data", exist_ok=True)  
        self.data = self._load_or_create()
        logging.debug(f"Trial file: {TRIAL_FILE}")

    # ------------------------------------------------------------------
    def _load_or_create(self):
        """Load existing file or create a fresh trial record."""
        if TRIAL_FILE.exists():
            try:
                token = TRIAL_FILE.read_bytes()
                plain = self.cipher.decrypt(token)
                data = json.loads(plain.decode())
                logging.debug(f"Trial data loaded: {data}")
                return data
            except Exception as e:
                logging.error(f"Corrupt trial.dat – recreating: {e}")
                TRIAL_FILE.unlink(missing_ok=True)

        # ---- FIRST RUN ----
        start = datetime.now().date().isoformat()
        data = {"start": start, "registered": False}
        self._save(data)
        logging.info(f"Created new trial.dat – start date: {start}")
        return data

    # ------------------------------------------------------------------
    def _save(self, data):
        payload = json.dumps(data).encode()
        token = self.cipher.encrypt(payload)
        TRIAL_FILE.write_bytes(token)

    # ------------------------------------------------------------------
    def is_registered(self) -> bool:
        return self.data.get("registered", False)

    # ------------------------------------------------------------------
    def days_left(self) -> int:
        if self.is_registered():
            return 999
        if TEST_OVERRIDE_DAYS_LEFT is not None:
            return max(0, TEST_OVERRIDE_DAYS_LEFT)

        start = datetime.fromisoformat(self.data["start"]).date()
        elapsed = (datetime.now().date() - start).days
        left = TRIAL_DAYS - elapsed
        return max(0, left)

    # ------------------------------------------------------------------
    def register(self, code: str) -> tuple[bool, str]:
        expected = self._make_code()
        if code.strip() == expected:
            self.data["registered"] = True
            self._save(self.data)
            logging.info("Registration successful")
            return True, "Registration successful!"
        return False, "Invalid code."

    # ------------------------------------------------------------------
    def _make_code(self) -> str:
        payload = f"{APP_NAME}|{AUTHOR}|{self.data['start']}"
        token = self.cipher.encrypt(payload.encode())
        return base64.urlsafe_b64encode(token).decode().rstrip("=")[:20]