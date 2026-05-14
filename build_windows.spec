# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas_qt, bins_qt, hidden_qt = collect_all('PyQt6')
datas_pg, bins_pg, hidden_pg = collect_all('pyqtgraph')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=bins_qt + bins_pg,
    datas=datas_qt + datas_pg + [('src', 'src')],
    hiddenimports=hidden_qt + hidden_pg + [
        'serial.tools.list_ports',
        'serial.tools.list_ports_windows',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'serial.tools.list_ports_posix'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SerialMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SerialMonitor',
)
