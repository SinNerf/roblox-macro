import os
import sys
import json
import time
import requests
import zipfile
import io
import shutil
import subprocess

def check_for_updates():
    """Check GitHub for updates (using GitHub Releases)"""
    try:
        # Your GitHub repository info
        owner = "SinNerf"  # Your GitHub username
        repo = "roblox-macro"  # Your repository name
        
        # Get latest release info
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(url)
        release = response.json()
        
        # Read current version
        current_version = "1.0.0"
        try:
            with open("version.txt", "r") as f:
                current_version = f.read().strip()
        except:
            pass
            
        # Compare versions
        latest_version = release["tag_name"].lstrip("v")
        if latest_version > current_version:
            return {
                "available": True,
                "version": latest_version,
                "url": release["assets"][0]["browser_download_url"]
            }
        return {"available": False}
    except Exception as e:
        print(f"Update check error: {str(e)}")
        return {"available": False, "error": str(e)}

def download_and_install_update(update_info):
    """Download and install the update"""
    try:
        # Download the ZIP file
        response = requests.get(update_info["url"])
        zip_data = io.BytesIO(response.content)
        
        # Extract to a temporary folder
        temp_dir = os.path.join(os.path.dirname(sys.executable), "update_temp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        with zipfile.ZipFile(zip_data, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Create batch file to handle the update after current app closes
        batch_content = f"""@echo off
timeout /t 2 /nobreak > NUL
echo Updating Roblox Macro Recorder to version {update_info["version"]}...
xcopy /E /Y "{temp_dir}\*" "{os.path.dirname(sys.executable)}\\"
rmdir /s /q "{temp_dir}"
echo Update complete!
echo Starting Roblox Macro Recorder...
start "" "{os.path.join(os.path.dirname(sys.executable), 'RobloxMacro.exe')}"
del "%~f0"
"""
        
        batch_path = os.path.join(os.path.dirname(sys.executable), "update.bat")
        with open(batch_path, "w") as f:
            f.write(batch_content)
        
        # Save new version info
        with open(os.path.join(os.path.dirname(sys.executable), "version.txt"), "w") as f:
            f.write(update_info["version"])
        
        return True
    except Exception as e:
        print(f"Update installation error: {str(e)}")
        return False

if __name__ == "__main__":
    update_info = check_for_updates()
    if update_info.get("available"):
        print(f"Update available: {update_info['version']}")
        if download_and_install_update(update_info):
            # Create a batch file to close the current app
            batch_content = """@echo off
taskkill /f /im RobloxMacro.exe
start "" "update.bat"
del "%~f0\""""
            
            batch_path = os.path.join(os.path.dirname(sys.executable), "close_and_update.bat")
            with open(batch_path, "w") as f:
                f.write(batch_content)
            
            # Run the batch file and exit
            subprocess.Popen(batch_path, shell=True)
            os._exit(0)
    else:
        print("No updates available")
        time.sleep(2)  # Give user time to see the message