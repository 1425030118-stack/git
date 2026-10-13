@echo off
setlocal
cd /d "%~dp0"

set "ENV_DIR=%~dp0.venv-local-translate"
set "PYTHON_EXE=%ENV_DIR%\Scripts\python.exe"
set "BASE_PYTHON=%LocalAppData%\Python\pythoncore-3.11-64\python.exe"

if not exist "%PYTHON_EXE%" (
    if exist "%BASE_PYTHON%" (
        "%BASE_PYTHON%" -m venv "%ENV_DIR%"
    ) else (
        where py >nul 2>nul
        if errorlevel 1 (
            echo Python 3.11 was not found. Install Python 3.11, then run this setup again.
            goto :failed
        )
        py -3.11 -m venv "%ENV_DIR%"
    )
    if errorlevel 1 goto :failed
)

echo Installing Argos Translate into the project's isolated environment...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :failed

"%PYTHON_EXE%" -m pip install argostranslate
if errorlevel 1 goto :failed

echo Downloading and checking the offline English-to-Chinese model...
"%PYTHON_EXE%" "%~dp0install_local_translation.py"
if errorlevel 1 goto :failed

echo.
echo Setup complete. Start the viewer with open_ranking_viewer.bat.
pause
exit /b 0

:failed
echo.
echo Local translation setup failed. Check the error above and your internet connection.
pause
exit /b 1
