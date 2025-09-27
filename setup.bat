@echo off
REM Tibia Launcher - Windows Installation Script
REM This script sets up the development environment and builds the launcher

echo ========================================
echo  Tibia Launcher Setup Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo ✓ Python found
python --version

echo.
echo Installing required packages...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages
    echo Try running: pip install PySide6 requests pyinstaller
    pause
    exit /b 1
)

echo ✓ Packages installed successfully
echo.

echo Testing the launcher...
echo Running launcher in test mode (will close automatically)...
timeout /t 2 >nul
python pyside6_gaming_launcher.py --test 2>nul

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit github_downloader.py - Update repo_owner and repo_name
echo 2. Replace images in images/ folder with your branding
echo 3. Create your launcher_config.json file in your GitHub repo
echo 4. Test: python pyside6_gaming_launcher.py
echo 5. Build: pyinstaller tibialauncher.spec --noconfirm
echo.
echo The built EXE will be in: dist\tibialauncher.exe
echo.
pause