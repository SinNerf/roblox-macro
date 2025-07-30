@echo off
setlocal enabledelayedexpansion

title Roblox Macro Updater Builder

echo Checking for required dependencies...

:: Check Python
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

:: Check if updater.py exists
if not exist "updater.py" (
    echo ERROR: updater.py not found!
    echo Please create updater.py or place it in this folder.
    echo You can use the template from the guide.
    pause
    exit /b 1
)

:: Install requests
echo Installing required packages (requests)...
pip install requests >nul 2>nul

:: Build with PyInstaller
echo Building updater executable...
pyinstaller --onefile --windowed --name "RobloxMacroUpdater" updater.py

:: Copy to root
if exist "dist\RobloxMacroUpdater.exe" (
    echo.
    echo Copying updater to current folder...
    copy /Y "dist\RobloxMacroUpdater.exe" "." >nul
    echo Updater built successfully: RobloxMacroUpdater.exe
) else (
    echo.
    echo ERROR: Build failed!
    echo Check above for PyInstaller errors.
    echo Common fixes:
    echo   - Run as Admin
    echo   - Disable antivirus temporarily
    echo   - Reinstall pyinstaller: pip install pyinstaller
    pause
    exit /b 1
)

echo.
echo Build complete!
echo Next:
echo   - Run release.bat to package a new version
echo   - Upload ZIP to GitHub under tag v1.2.3
pause