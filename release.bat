@echo off
setlocal enabledelayedexpansion

title Roblox Macro - Release Builder

:: Read current version
set "CURRENT_VERSION=1.0.0"
if exist "version.txt" (
    set /p CURRENT_VERSION=<version.txt
)

:: Prompt for new version
echo.
echo Current version: %CURRENT_VERSION%
set /p "NEW_VERSION=Enter new version (format X.X.X, e.g., 1.0.1): "

:: Validate version format (must be X.X.X)
echo %NEW_VERSION% | findstr /r "^[0-9]*\.[0-9]*\.[0-9]*$" >nul
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Invalid version format. Use numbers and dots only: X.X.X
    echo Example: 1.0.1
    pause
    exit /b 1
)

:: Confirm
echo.
echo Creating version: %NEW_VERSION%
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

:: Update version.txt
echo %NEW_VERSION% > version.txt

:: Run build script (assumes you have build.bat that creates the app)
echo.
echo Building Roblox Macro application...
call build.bat

:: Create build folder
if not exist "build" mkdir build

:: Create ZIP
echo.
echo Creating ZIP package...
set "ZIP_NAME=RobloxMacro_v%NEW_VERSION%.zip"
cd /d "build"
powershell -Command "Remove-Item '%ZIP_NAME%' -ErrorAction Ignore"
cd ..
powershell -Command "Compress-Archive -Path 'RobloxMacro_*\*' -DestinationPath 'build\%ZIP_NAME%' -Force"

:: Show release instructions
echo.
echo ====================================================
echo RELEASE INSTRUCTIONS
echo ====================================================
echo 1. Go to: https://github.com/SinNerf/roblox-macro/releases
echo 2. Click "Draft a new release"
echo 3. Tag: v%NEW_VERSION%
echo 4. Title: Version %NEW_VERSION%
echo 5. Description: New update available!
echo 6. Upload file:
echo    %cd%\build\%ZIP_NAME%
echo 7. Publish release
echo.
echo ✅ Users will auto-update via RobloxMacroUpdater.exe!
echo.
echo Opening build folder...
explorer "build"
pause