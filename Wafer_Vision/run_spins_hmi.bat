@echo off
setlocal

cd /d "%~dp0"

set "VENV_DIR=%~dp0venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo.
    echo [ERROR] venv not found: "%PYTHON_EXE%"
    echo [INFO] Create the virtual environment first, then run this file again.
    pause
    exit /b 1
)

echo [INFO] Launching SPINS Integrated HMI...
"%PYTHON_EXE%" "%~dp0main_ui.py"
set "APP_EXIT_CODE=%ERRORLEVEL%"

if not "%APP_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] SPINS HMI exited with code %APP_EXIT_CODE%.
    pause
)

exit /b %APP_EXIT_CODE%
