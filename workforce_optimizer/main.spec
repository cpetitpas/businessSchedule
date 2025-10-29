# main.spec
# -*- mode: python ; coding: utf-8 -*-

import os, glob
import pulp
from pathlib import Path

block_cipher = None

# ---------------------------------------------------------------
# 1. Find CBC and define EXACT target path
# ---------------------------------------------------------------
def find_cbc():
    try:
        solver = pulp.PULP_CBC_CMD(msg=False)
        if solver.path and Path(solver.path).exists():
            return solver.path
    except:
        pass

    # Fallback search
    search = [
        Path(os.path.expanduser("~")) / ".pulp" / "solvers" / "CBC" / "win64" / "cbc.exe",
        Path(pulp.__file__).parent / "solverdir" / "cbc-win64.exe",
    ]
    for p in search:
        if p.exists():
            return str(p)
    
    raise FileNotFoundError("CBC not found. Run: python -m pulp --install-cbc")

CBC_SOURCE = find_cbc()
CBC_TARGET_DIR = 'pulp/solverdir/cbc/win/i64'  # EXACT PATH PuLP expects
CBC_TARGET = os.path.join(CBC_TARGET_DIR, 'cbc.exe')

# ---------------------------------------------------------------
# 2. Collect datas
# ---------------------------------------------------------------
datas = []
for folder in ['images', 'data']:
    if os.path.isdir(folder):
        for p in glob.glob(os.path.join(folder, '**', '*.*'), recursive=True):
            dest = os.path.relpath(os.path.dirname(p), folder)
            dest = folder if dest == '.' else os.path.join(folder, dest)
            datas.append((p, dest))
datas.append((r'icons\teamwork.ico', 'icons'))  # Bundle icon

# ---------------------------------------------------------------
# 3. Analysis — Bundle CBC into EXACT path
# ---------------------------------------------------------------
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        (CBC_SOURCE, CBC_TARGET_DIR),  # This creates the correct folder
    ],
    datas=datas,
    hiddenimports=[
        'pulp',
        'pulp.apis',
        'pulp.apis.coin_api',
        'pulp.solvers',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='WorkforceOptimizer',
    debug=False,
    console=False,
    icon=r'icons\teamwork.ico',
    onefile=True,
)