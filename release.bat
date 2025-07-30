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

:: DEBUG: Show exactly what was entered
echo DEBUG: You entered: "%NEW_VERSION%"
echo DEBUG: Length: %NEW_VERSION:~0,1%

:: Trim whitespace from input
set "NEW_VERSION=%NEW_VERSION: =%"
set "NEW_VERSION=%NEW_VERSION:"=%"
set "NEW_VERSION=%NEW_VERSION:`=%"
set "NEW_VERSION=%NEW_VERSION:'=%"

:: DEBUG: Show cleaned version
echo DEBUG: Cleaned version: "%NEW_VERSION%"

:: Validate version format - SIMPLE AND RELIABLE METHOD
set "VALID=true"

:: Check for exactly two dots
set "dot_count=0"
for /f "delims=" %%a in ('echo %NEW_VERSION% ^| find /c "."') do set "dot_count=%%a"

if !dot_count! neq 2 (
    set "VALID=false"
    echo ERROR: Version must be in format X.X.X (e.g., 1.0.0) with exactly two dots
    echo Your input: %NEW_VERSION%
    echo Expected format: major.minor.patch (e.g., 1.0.1)
)

:: Check for invalid characters
echo %NEW_VERSION% | findstr /r "[^0-9\.]" >nul
if !errorlevel! equ 0 (
    :: This is correct - errorlevel 0 means match found (invalid characters)
    set "VALID=false"
    echo ERROR: Version must contain only digits and dots
    echo Your input: %NEW_VERSION%
)

:: Check if version is greater than current
for /f "tokens=1-3 delims=." %%a in ("%NEW_VERSION%") do (
    for /f "tokens=1-3 delims=." %%x in ("%CURRENT_VERSION%") do (
        if %%a lss %%x set "VALID=false"
        if %%a equ %%x (
            if %%b lss %%y set "VALID=false"
            if %%b equ %%y (
                if %%c leq %%z set "VALID=false"
            )
        )
    )
)
if "!VALID!"=="false" (
    echo ERROR: New version must be greater than current version (%CURRENT_VERSION%)
)

:: Exit if invalid
if "!VALID!"=="false" (
    echo.
    echo Please correct the version format and try again.
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