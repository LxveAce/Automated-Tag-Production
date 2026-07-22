
@echo off
setlocal enableextensions

set "APP_PY=Automated Tag Creator V5 by LxveAce -Source Code.py"
set "APP_NAME=Automated Tag Creator V5 by LxveAce"
set "VENV_DIR=.venv"
set "PYTHONNOUSERSITE=1"

REM Non-synced build locations (avoid OneDrive)
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "BUILD_ROOT=%LOCALAPPDATA%\AutomatedTagCreator\pyi"
set "WORK_DIR=%BUILD_ROOT%\work"
set "DIST_DIR=%BUILD_ROOT%\dist"
set "SPEC_DIR=%BUILD_ROOT%\spec"

echo === Automated Tag Creator one-click build (OneDrive-safe) ===

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH. Install Python 3.11/3.12 and re-run.
  pause
  exit /b 1
)

if not exist "%VENV_DIR%" (
  echo Creating virtual environment...
  python -m venv "%VENV_DIR%"
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [ERROR] venv python not found at %VENV_PY%
  pause
  exit /b 1
)

echo Preparing local build folders...
mkdir "%WORK_DIR%" 2>nul
mkdir "%DIST_DIR%" 2>nul
mkdir "%SPEC_DIR%" 2>nul

echo Upgrading pip in venv...
"%VENV_PY%" -m pip install --upgrade pip

if exist requirements.txt (
  echo Installing requirements from requirements.txt into venv...
  "%VENV_PY%" -m pip install -r requirements.txt
) else (
  echo Installing requirements into venv...
  "%VENV_PY%" -m pip install customtkinter pandas reportlab pillow pyinstaller
)

set ICON_FLAG=
if exist "icon.ico" (
  set ICON_FLAG=--icon "icon.ico"
  echo Using icon.ico
)

REM Optional: include extra data files (templates, fonts). Example:
REM set ADD_DATA=--add-data "templates\default.json;templates" --add-data "fonts\MyFont.ttf;fonts"
set ADD_DATA=

>version.txt echo %APP_NAME% build on %date% %time%

echo Building EXE with PyInstaller from venv (OneDrive-safe paths)...
"%VENV_PY%" -m PyInstaller ^
  --noconfirm --onefile --windowed --clean ^
  --name "%APP_NAME%" %ICON_FLAG% %ADD_DATA% ^
  --workpath "%WORK_DIR%" --distpath "%DIST_DIR%" --specpath "%SPEC_DIR%" ^
  "%APP_PY%"

if errorlevel 1 (
  echo [ERROR] PyInstaller build failed.
  echo If this persists, close any open Explorer windows showing the project folder and retry.
  pause
  exit /b 1
)

if exist "%DIST_DIR%\%APP_NAME%.exe" (
  echo Build complete.
  echo Output: "%DIST_DIR%\%APP_NAME%.exe"
) else (
  echo Build finished, but output EXE not found in "%DIST_DIR%". Check PyInstaller logs.
)

pause
endlocal
