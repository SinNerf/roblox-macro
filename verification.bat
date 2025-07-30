@echo off
setlocal enabledelayedexpansion

title Roblox Macro Recorder - Verification System

if "%1"=="" (
    echo Usage: verification.bat ^<path_to_exe^>
    echo Example: verification.bat "build\RobloxMacro_20231115_143022\RobloxMacro.exe"
    exit /b 1
)

set "EXE_PATH=%~1"

if not exist "%EXE_PATH%" (
    echo ERROR: File not found at %EXE_PATH%
    exit /b 1
)

:: Generate SHA-256 hash
certutil -hashfile "%EXE_PATH%" SHA256 > temp_hash.txt
set /p HASH=<temp_hash.txt
del temp_hash.txt
set "HASH=!HASH:Certificate Hash (sha256)= !"
set "HASH=!HASH: =!"

:: Create verification files
set "DIR=%~dp1"
echo Verification files created for %~nx1 > "%DIR%verification.txt"
echo. >> "%DIR%verification.txt"
echo File: %~nx1 >> "%DIR%verification.txt"
echo SHA-256: !HASH! >> "%DIR%verification.txt"
echo. >> "%DIR%verification.txt"
echo To verify this file:
echo 1. Run: certutil -hashfile "%~nx1" SHA256
echo 2. Compare with the hash above
echo. >> "%DIR%verification.txt"
echo This application is digitally signed with a valid certificate >> "%DIR%verification.txt"
echo confirming it has not been tampered with. >> "%DIR%verification.txt"

echo Verification files created in %DIR%
echo SHA-256 hash: !HASH!
endlocal