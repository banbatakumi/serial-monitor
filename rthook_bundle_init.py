# PyInstaller runtime hook: pre-initialize macOS bundle before Qt loads.
# CFBundleGetMainBundle() returns NULL during Qt's static initializers on
# macOS 26 when AppKit has not yet been loaded by the bootloader.
import ctypes
import sys

if sys.platform == "darwin":
    try:
        # Loading AppKit triggers NSApplication/CFBundle initialization so
        # CFBundleGetMainBundle() is non-NULL when QtCore.abi3.so is dlopen'd.
        ctypes.CDLL("/System/Library/Frameworks/AppKit.framework/AppKit")

        # Explicitly touch CFBundleGetMainBundle to complete initialization.
        cf = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        cf.CFBundleGetMainBundle.restype = ctypes.c_void_p
        cf.CFBundleGetMainBundle()
    except Exception:
        pass
