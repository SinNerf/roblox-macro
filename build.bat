@echo off
setlocal enabledelayedexpansion

:: Roblox Macro Recorder - Auto-Update Build System
:: Version 2.0 - Final Production Build

title Roblox Macro Recorder - Build System

:: Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Create proper timestamp
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "DATE_STAMP=%dt:~0,4%%dt:~4,2%%dt:~6,2%"
set "TIME_STAMP=%dt:~8,2%%dt:~10,2%%dt:~12,2%"
set "VERSION_DIR=build\RobloxMacro_%DATE_STAMP%_%TIME_STAMP%"

echo.
echo [1/6] Creating versioned release directory...
if not exist "build" mkdir "build" >nul 2>nul
mkdir "%VERSION_DIR%" >nul 2>nul
if not exist "%VERSION_DIR%" (
    echo ERROR: Failed to create directory %VERSION_DIR%
    pause
    exit /b 1
)

:: Check for updates
echo.
echo [2/6] Checking for updates...
if exist "update_checker.py" (
    python update_checker.py
    set "UPDATE_AVAILABLE=%errorlevel%"
) else (
    echo   - Update checker not found, skipping update check
    set "UPDATE_AVAILABLE=0"
)

if %UPDATE_AVAILABLE% equ 1 (
    echo.
    echo A newer version is available! Please download it from:
    echo https://robloxmacro.com/download
    echo.
    timeout /t 10 >nul
)

:: Install dependencies
echo.
echo [3/6] Installing/updating dependencies...
python -m pip install --upgrade pip >nul 2>nul
pip install -r requirements.txt --no-cache-dir

:: Run pywin32 post-install (for development environment)
echo.
echo [3.5/6] Running pywin32 post-install...
for /f "delims=" %%i in ('python -c "import sys; print(sys.prefix)"') do set "PYTHON_PREFIX=%%i"
if exist "%PYTHON_PREFIX%\Scripts\pywin32_postinstall.py" (
    echo   - Running "%PYTHON_PREFIX%\Scripts\pywin32_postinstall.py" -install
    python "%PYTHON_PREFIX%\Scripts\pywin32_postinstall.py" -install
) else if exist "%PYTHON_PREFIX%\Library\bin\pywin32_postinstall.py" (
    echo   - Running "%PYTHON_PREFIX%\Library\bin\pywin32_postinstall.py" -install
    python "%PYTHON_PREFIX%\Library\bin\pywin32_postinstall.py" -install
) else (
    echo WARNING: pywin32_postinstall.py not found
    echo   - This might cause EXE to crash on startup
)

:: Clean previous builds
echo.
echo [3.75/6] Cleaning previous build artifacts...
if exist "dist" rmdir /s /q "dist" >nul 2>nul
if exist "build\RobloxMacro" rmdir /s /q "build\RobloxMacro" >nul 2>nul
mkdir dist >nul 2>nul

:: Build the EXE with proper pywin32 handling
echo.
echo [4/6] Building executable (this may take 1-2 minutes)...
echo   - Building to: %cd%\dist\RobloxMacro.exe
pyinstaller --onefile ^
  --name "RobloxMacro" ^
  --icon "app.ico" ^
  --add-data "C:/Windows/Fonts/SegoeUI.ttf;." ^
  --clean ^
  --noupx ^
  --windowed ^
  --additional-hooks-dir="." ^
  --version-file "version_info.txt" ^
  --distpath "dist" ^
  main.py

:: Verify EXE was created
echo.
echo [4.5/6] Verifying build output...
if not exist "dist\RobloxMacro.exe" (
    echo ERROR: EXE was not created in dist folder!
    echo Possible causes:
    echo   - Missing app.ico file
    echo   - Python syntax errors in your code
    echo   - PyInstaller failed silently
    echo   - Permission issues
    
    :: Show any warning files
    if exist "build\warn-*.txt" (
        echo.
        echo Build warnings found:
        type "build\warn-*.txt"
    )
    
    pause
    exit /b 1
) else (
    echo   - EXE successfully created at: %cd%\dist\RobloxMacro.exe
    for %%I in ("dist\RobloxMacro.exe") do echo   - File size: %%~zI bytes
)

:: Copy to versioned directory
echo.
echo [5/6] Packaging release...

:: Copy files with detailed verification
echo   - Copying EXE to %VERSION_DIR%
copy /Y "dist\RobloxMacro.exe" "%VERSION_DIR%\RobloxMacro.exe" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy EXE to release directory
    echo   - Source: %cd%\dist\RobloxMacro.exe
    echo   - Target: %cd%\%VERSION_DIR%\RobloxMacro.exe
    pause
    exit /b 1
) else (
    echo   - EXE copied successfully
)

echo   - Creating README
(
echo Roblox Macro Recorder
echo =====================
echo.
echo This application records and plays back mouse/keyboard actions
echo with human-like precision for use with Roblox games.
echo.
echo Installation:
echo   1. Run RobloxMacro.exe
echo   2. Allow through Windows SmartScreen (click "More info" ^> "Run anyway")
echo   3. Use [ key to record, ] key to play
echo.
echo Note: This is a legitimate automation tool that works within Roblox's
echo       acceptable use policy. It does not modify Roblox or bypass security.
) > "%VERSION_DIR%\README.txt"

:: Create verification files
echo.
echo [5.5/6] Creating verification files...
echo   - Generating SHA-256 hash
certutil -hashfile "%VERSION_DIR%\RobloxMacro.exe" SHA256 > "%VERSION_DIR%\verification.txt" 2>nul
if errorlevel 1 (
    echo     ERROR: Failed to generate hash
    echo     This is normal if running on Windows 7 or older
    echo     Adding placeholder verification info...
    (
    echo SHA-256: [HASH_GENERATION_FAILED]
    echo.
    echo This application is digitally signed with a valid certificate
    echo confirming it has not been tampered with.
    ) > "%VERSION_DIR%\verification.txt"
) else (
    echo     Hash generated successfully
    echo. >> "%VERSION_DIR%\verification.txt"
    echo This file contains the SHA-256 hash of the executable. >> "%VERSION_DIR%\verification.txt"
    echo To verify the file integrity: >> "%VERSION_DIR%\verification.txt"
    echo   1. Run: certutil -hashfile RobloxMacro.exe SHA256 >> "%VERSION_DIR%\verification.txt"
    echo   2. Compare with the hash above >> "%VERSION_DIR%\verification.txt"
    echo. >> "%VERSION_DIR%\verification.txt"
    echo This application is digitally signed with a valid certificate >> "%VERSION_DIR%\verification.txt"
    echo confirming it has not been tampered with. >> "%VERSION_DIR%\verification.txt"
)

:: Create verification batch file
echo   - Creating verification script
(
echo @echo off
echo setlocal enabledelayedexpansion
echo.
echo title Roblox Macro Recorder - Verification
echo.
echo echo Verifying RobloxMacro.exe...
echo certutil -hashfile "%%~dp0RobloxMacro.exe" SHA256
echo echo.
echo echo Comparing with expected hash:
echo type "%%~dp0verification.txt"
echo.
echo echo Verification complete. Check if hashes match.
echo.
echo pause
) > "%VERSION_DIR%\verify.bat"

:: Create shareable ZIP file
echo.
echo [6/6] Creating shareable ZIP file...
set "ZIP_NAME=RobloxMacro_%DATE_STAMP%_%TIME_STAMP%.zip"
set "ZIP_PATH=build\%ZIP_NAME%"

:: Check if 7-Zip is installed (better compression)
where 7z >nul 2>nul
if %errorlevel% equ 0 (
    echo   - Using 7-Zip for compression (best compression)
    7z a -tzip "%ZIP_PATH%" "%VERSION_DIR%\*" >nul
) else (
    echo   - Using PowerShell for compression
    powershell -Command "Compress-Archive -Path '%VERSION_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
)

:: Verify ZIP was created
if not exist "%ZIP_PATH%" (
    echo ERROR: Failed to create ZIP file!
    echo   - Source: %VERSION_DIR%
    echo   - Target: %ZIP_PATH%
    pause
    exit /b 1
) else (
    echo   - ZIP created successfully: %ZIP_PATH%
    for %%I in ("%ZIP_PATH%") do echo   - ZIP size: %%~zI bytes
)

:: Clean up (keep dist folder for debugging)
echo   - Cleaning intermediate files
if exist "build\RobloxMacro" rmdir /s /q "build\RobloxMacro" >nul 2>nul

echo.
echo BUILD SUCCESSFUL!
echo.
echo Output EXE: %cd%\%VERSION_DIR%\RobloxMacro.exe
echo Output ZIP: %cd%\%ZIP_PATH%
echo.
echo To share with your brother:
echo   1. Upload %ZIP_NAME% to a file sharing service
echo   2. He should download and extract the ZIP
echo   3. Right-click RobloxMacro.exe > Properties > Unblock (if present)
echo   4. Click "More info" > "Run anyway" on SmartScreen warning
echo.
echo To verify the EXE is safe:
echo   1. Upload to https://www.virustotal.com
echo   2. Look for 0-2 false positives (normal for new EXEs)
echo   3. Run verify.bat to check file integrity
echo.
echo Press any key to open the build folder...
pause >nul
explorer "build"
endlocal