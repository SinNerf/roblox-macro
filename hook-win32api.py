# hook-win32api.py
from PyInstaller.utils.hooks import collect_dynamic_libs

# This tells PyInstaller to include all necessary DLLs for win32api
binaries = collect_dynamic_libs('pywin32')