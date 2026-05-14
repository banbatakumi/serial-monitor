# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import pyqtgraph

pg_root = str(Path(pyqtgraph.__file__).parent)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        (pg_root, 'pyqtgraph'),
    ],
    hiddenimports=[
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.graphicsItems.PlotItem',
        'pyqtgraph.graphicsItems.LegendItem',
        'pyqtgraph.graphicsItems.ViewBox',
        'pyqtgraph.graphicsItems.AxisItem',
        'pyqtgraph.graphicsItems.GraphicsLayout',
        'pyqtgraph.widgets',
        'pyqtgraph.widgets.PlotWidget',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'serial.tools.list_ports_posix',
        'numpy',
        'numpy.core._multiarray_umath',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'PyQt6.QtOpenGL',
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_bundle_init.py'],
    excludes=['tkinter', 'matplotlib'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SerialMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SerialMonitor',
)

app = BUNDLE(
    coll,
    name='SerialMonitor.app',
    icon=None,
    bundle_identifier='com.banbatakumi.serialmonitor',
    version='1.0.2',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': True,
        'CFBundleDisplayName': 'Serial Monitor',
        'CFBundleShortVersionString': '1.0.2',
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
        'NSBluetoothAlwaysUsageDescription': '',
    },
)
