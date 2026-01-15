# tests/conftest.py
import pytest
from tkinter import messagebox

@pytest.fixture(autouse=True)
def no_messagebox(monkeypatch):
    """Prevent all tkinter messagebox calls during tests"""
    def fake_yesnocancel(title, message, **kwargs):
        # For "File exists - Overwrite?" we always choose Yes (overwrite)
        if "File already exists" in message:
            return True  # Yes → overwrite
        return None  # or False/Cancel for others

    def fake_showinfo(*args, **kwargs):
        pass  # silent

    def fake_showerror(*args, **kwargs):
        pass

    monkeypatch.setattr(messagebox, "askyesnocancel", fake_yesnocancel)
    monkeypatch.setattr(messagebox, "showinfo", fake_showinfo)
    monkeypatch.setattr(messagebox, "showerror", fake_showerror)
    monkeypatch.setattr(messagebox, "showwarning", fake_showinfo)