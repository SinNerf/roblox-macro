@echo off
setlocal enabledelayedexpansion

title Roblox Macro - Release Builder

:: Get current version
set "CURRENT_VERSION=1.0.0"
if exist "version.txt" (
    set /p CURRENT_VERSION=<version.txt
)

:: Prompt for new version
echo Current version: %CURRENT_VERSION%
set /p "NEW_VERSION=Enter new version (e.g., 1.0.1): "

:: Validate version format - SIMPLER AND MORE RELIABLE METHOD
set "dot_count=0"
for /f "delims=" %%a in ('echo %NEW_VERSION% ^| find /c "."') do set "dot_count=%%a"

:: Check for invalid characters (anything that's not a digit or dot)
echo %NEW_VERSION% | findstr /r "[^0-9\.]" >nul
if %errorlevel% equ 0 (
    echo ERROR: Version must contain only digits and dots
    pause
    exit /b 1
)

if %dot_count% neq 2 (
    echo ERROR: Version must be in format X.X.X (e.g., 1.0.0) with exactly two dots
    echo Your input: %NEW_VERSION%
    echo Expected format: major.minor.patch (e.g., 1.0.1)
    pause
    exit /b 1
)

:: Update version file
echo %NEW_VERSION% > version.txt

:: Build the application
echo.
echo Building application...
call build.bat

:: Create ZIP of the build
echo.
echo Creating ZIP file...
set "ZIP_NAME=RobloxMacro_v%NEW_VERSION%.zip"
cd build
powershell -Command "Compress-Archive -Path 'RobloxMacro_*\*' -DestinationPath '%ZIP_NAME%' -Force"
cd ..

:: Instructions for manual GitHub release
echo.
echo RELEASE INSTRUCTIONS:
echo =====================
echo 1. Go to your GitHub repository: https://github.com/SinNerf/roblox-macro
echo 2. Click "Releases" > "Draft a new release"
echo 3. Tag version: v%NEW_VERSION%
echo 4. Release title: "Version %NEW_VERSION%"
echo 5. Description: "New version of Roblox Macro Recorder"
echo 6. Drag and drop this file to upload:
echo    %cd%\build\%ZIP_NAME%
echo 7. Click "Publish release"
echo.
echo USERS WILL AUTOMATICALLY GET THIS UPDATE WHEN THEY RUN THE UPDATER!
echo.
echo Press any key to open the build folder and copy the ZIP file path...
pause >nul
explorer "build"
endlocal