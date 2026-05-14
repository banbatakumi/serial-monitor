from setuptools import setup

APP = ['main.py']

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'packages': [
        'src',
        'PyQt6',
        'pyqtgraph',
        'serial',
        'numpy',
    ],
    'includes': [
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'PyQt6.QtOpenGL',
        'PyQt6.sip',
        'serial.tools.list_ports',
        'serial.tools.list_ports_posix',
    ],
    'excludes': ['tkinter', 'matplotlib'],
    'plist': {
        'CFBundleName': 'SerialMonitor',
        'CFBundleDisplayName': 'Serial Monitor',
        'CFBundleIdentifier': 'com.banbatakumi.serialmonitor',
        'CFBundleVersion': '1.0.4',
        'CFBundleShortVersionString': '1.0.4',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
        'NSBluetoothAlwaysUsageDescription': 'Bluetooth is not used.',
        'NSLocationWhenInUseUsageDescription': 'Location is not used.',
        'NSMicrophoneUsageDescription': 'Microphone is not used.',
        'NSCameraUsageDescription': 'Camera is not used.',
    },
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
