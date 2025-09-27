@echo off
REM Tibia Launcher - Build Script
REM This script builds the launcher executable with proper configuration

setlocal enabledelayedexpansion

echo ========================================
echo  Tibia Launcher Build Script
echo ========================================
echo.

REM Check if required files exist
if not exist "pyside6_gaming_launcher.py" (
    echo ERROR: Main launcher file not found
    echo Make sure you're running this from the launcher directory
    pause
    exit /b 1
)

if not exist "tibialauncher.spec" (
    echo ERROR: PyInstaller spec file not found
    pause
    exit /b 1
)

REM Check Python and packages
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Run setup.bat first
    pause
    exit /b 1
)

echo ✓ Python found
python --version

echo.
echo Checking required packages...
python -c "import PySide6; print('✓ PySide6')" 2>nul || (
    echo ERROR: PySide6 not installed. Run: pip install PySide6
    pause
    exit /b 1
)

python -c "import requests; print('✓ requests')" 2>nul || (
    echo ERROR: requests not installed. Run: pip install requests
    pause
    exit /b 1
)

python -c "import PyInstaller; print('✓ PyInstaller')" 2>nul || (
    echo ERROR: PyInstaller not installed. Run: pip install pyinstaller
    pause
    exit /b 1
)

echo.
echo Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo.
echo Building launcher executable...
echo This may take a few minutes...
pyinstaller tibialauncher.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed
    echo Check the output above for errors
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build Successful!
echo ========================================
echo.

if exist "dist\tibialauncher.exe" (
    for %%I in ("dist\tibialauncher.exe") do (
        echo EXE Location: %%~fI
        echo File Size: %%~zI bytes
        echo Created: %%~tI
    )
    echo.
    echo ✓ Launcher built successfully!
    echo.
    echo Next steps:
    echo 1. Test the EXE: dist\tibialauncher.exe
    echo 2. Optional: Sign the EXE to avoid SmartScreen warnings
    echo 3. Upload to your website
    echo 4. Update your launcher_config.json with the download URL
    echo.
    
    set /p "test=Do you want to test the launcher now? (y/n): "
    if /i "!test!"=="y" (
        echo Testing launcher...
        start dist\tibialauncher.exe
    )
) else (
    echo ERROR: Build completed but EXE not found
    echo Check the dist/ folder manually
)

echo.
pause