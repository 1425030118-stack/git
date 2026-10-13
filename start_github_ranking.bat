@echo off
cd /d "%~dp0"
set "NO_PAUSE="
if /i "%~1"=="/nopause" set "NO_PAUSE=1"

if not exist "access_token.txt" (
    echo GitHub Token not found.
    echo Please create a file named access_token.txt in the project root.
    echo Example: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    echo.
    echo Opening template for editing...
    type nul > access_token.txt
    notepad access_token.txt
    exit /b 1
)

for %%I in ("access_token.txt") do if %%~zI==0 (
    echo GitHub Token is empty.
    echo Please paste your GitHub token into access_token.txt.
    echo Example: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    echo.
    echo Opening file for editing...
    notepad access_token.txt
    exit /b 1
)

if exist "%~dp0.venv-local-translate\Scripts\python.exe" (
    "%~dp0.venv-local-translate\Scripts\python.exe" "%~dp0source\process.py"
    goto :check_result
)

if exist "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" (
    "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" "%~dp0source\process.py"
    goto :check_result
)

if exist "%LocalAppData%\Python\pythoncore-3.11-64\python.exe" (
    "%LocalAppData%\Python\pythoncore-3.11-64\python.exe" "%~dp0source\process.py"
    goto :check_result
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0source\process.py"
    goto :check_result
)

where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0source\process.py"
    goto :check_result
)

echo Python 3 was not found. Install Python 3 or run setup_local_translation.bat.
if not defined NO_PAUSE pause
exit /b 1

:check_result
if errorlevel 1 (
    echo.
    echo The program failed. Please check the token and network connection.
    if not defined NO_PAUSE pause
    exit /b 1
)
exit /b 0
