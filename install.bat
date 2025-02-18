@echo off
setlocal

; set "HTTPS_PROXY=http://127.0.0.1:3128"
; set "HTTP_PROXY=http://127.0.0.1:3128"
; set "PIP_PROXY=http://127.0.0.1:3128"

echo Setting up the virtual environment...
%SystemRoot%\py.exe -m venv venv || (
    echo Failed to create virtual environment.
    exit /b 1
)

echo Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
venv\Scripts\python.exe -m pip install -r requirements-windows.txt || (
    echo Failed to install dependencies.
    exit /b 1
)

echo Running siracusa.py...
venv\Scripts\python.exe siracusa.py || (
    echo Script execution failed.
    exit /b 1
)

echo Done.
endlocal
