# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for SINGLE-FILE build of lunarialauncher.exe
Build:
  pyinstaller lunarialauncher_onefile.spec
Result:
  dist/lunarialauncher.exe (one file)
Notes:
  - Slower startup (extracts to temp)
  - AV false positives more likely
  - Uses resource_path helper already in code
"""
import os
from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "tibialauncher"
ENTRY_SCRIPT = "pyside6_gaming_launcher.py"
ICON_PATH = "images/appicon.ico" if os.path.exists("images/appicon.ico") else None

hidden_imports = collect_submodules('PySide6')

datas = [
  ('images/*.png', 'images'),
  ('images/*.ico', 'images'),
  ('config/*', 'config'),
]

block_cipher = None

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[],
    binaries=[],
  datas=datas,
  hiddenimports=hidden_imports + ['tibialauncher', 'tibialauncher.core', 'tibialauncher.core.launcher_core', 'tibialauncher.core.github_downloader', 'tibialauncher.core.file_manager'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
  icon=ICON_PATH,
  version='version_info.txt',
)

# One file bundle
onefile = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
  icon=ICON_PATH,
  version='version_info.txt',
    append_pkg=False,
    runtime_tmpdir=None,
)
