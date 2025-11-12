# main.spec
# -*- mode: python ; coding: utf-8 -*-
import os, glob
import pulp
from pathlib import Path

block_cipher = None

def find_cbc():
    try:
        solver = pulp.PULP_CBC_CMD(msg=False)
        if solver.path and Path(solver.path).exists():
            return solver.path
    except: pass
    search = [
        Path(os.path.expanduser("~")) / ".pulp" / "solvers" / "CBC" / "win64" / "cbc.exe",
        Path(pulp.__file__).parent / "solverdir" / "cbc-win64.exe",
    ]
    for p in search:
        if p.exists():
            return str(p)
    raise FileNotFoundError("CBC not found")

CBC_SOURCE = find_cbc()
CBC_TARGET_DIR = 'pulp/solverdir/cbc/win/i64'

datas = []
for folder in ['images', 'data', 'docs']:
    if os.path.isdir(folder):
        for p in glob.glob(os.path.join(folder, '**', '*.*'), recursive=True):
            dest = os.path.relpath(os.path.dirname(p), folder)
            dest = folder if dest == '.' else os.path.join(folder, dest)
            datas.append((p, dest))
datas.append((r'icons\teamwork.ico', 'icons'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(CBC_SOURCE, CBC_TARGET_DIR)],
    datas=datas,
    hiddenimports=['pulp', 'pulp.apis', 'pulp.apis.coin_api', 'pulp.solvers'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
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
    onefile=False,  # ← ONEDIR ONLY
    upx=True,
)