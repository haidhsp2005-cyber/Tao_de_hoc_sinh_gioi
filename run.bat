@echo off
chcp 65001 > nul
title OLYMPIAD PROBLEM FORGE - HE THONG TAO DE THI HSG TIN HOC
setlocal enabledelayedexpansion

:: 1. Chuyen ngay ve thu muc chua file run.bat
cd /d "%~dp0"

echo ================================================================
echo    OLYMPIAD PROBLEM FORGE - HE THONG TAO DE THI HSG TIN HOC
echo    Khoi chay AI Agent (Ollama Offline + Google Gemini Cloud)
echo ================================================================
echo.

:: 2. Tim kiem trinh thuc thi Python chinh xac tren may
set "PY_CMD="

python -c "import sys; print(sys.version)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
)

if not defined PY_CMD (
    if exist "C:\ProgramData\miniconda3\python.exe" (
        set "PY_CMD=C:\ProgramData\miniconda3\python.exe"
    )
)

if not defined PY_CMD (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
    )
)

if not defined PY_CMD (
    echo ================================================================
    echo [LOI] Khong tim thay Python tren may tinh cua ban!
    echo Vui long kiem tra lai duong dan Python hoac cai dat Miniconda.
    echo ================================================================
    pause
    exit /b 1
)

echo [OK] Su dung Python tai: !PY_CMD!
echo [OK] Thu muc du an: %~dp0
echo.
echo Dang khoi dong Web Server tren http://localhost:5000 ...
echo (Trinh duyet web se tu dong mo sau 2 giay...)
echo.

:: 3. Doi 2 giay de Web Server khoi dong xong roi moi mo trinh duyet
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"

:: 4. Khoi chay Web Server chinh
"!PY_CMD!" -u server.py

if !errorlevel! neq 0 (
    echo.
    echo ================================================================
    echo [THONG BAO] Server da dung hoac gap loi (Ma loi: !errorlevel!).
    echo ================================================================
)
echo.
pause
