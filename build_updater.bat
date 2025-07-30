@echo off
echo Building updater...
pyinstaller --onefile --windowed --name "RobloxMacroUpdater" updater.py
echo.
echo Updater built successfully!
echo Output: dist\RobloxMacroUpdater.exe
echo.
echo To use:
echo 1. Place this EXE in the same folder as your main application
echo 2. Run it to check for updates
echo 3. It will automatically update when available
pause