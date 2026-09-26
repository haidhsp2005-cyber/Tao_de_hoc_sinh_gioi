@echo off
chcp 65001 > nul
title DAY MA NGUON LEN GITHUB DE TRIEN KHAI RENDER
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ======================================================================
echo    CONG CU DAY MA NGUON LEN GITHUB DE TRIEN KHAI LEN RENDER.COM
echo ======================================================================
echo.
echo [1] Neu ban chua co Repository tren GitHub, hay truy cap:
echo     https://github.com/new
echo     Tao mot repo moi (vi du: olympiad-exam-generator) - che do Public hoac Private deu duoc.
echo.
echo [2] Dan duong dan URL cua Repository GitHub vao ben duoi:
echo     (Vi du: https://github.com/your-username/olympiad-exam-generator.git)
echo.

set /p REPO_URL=">> Nhap GitHub Repository URL: "

if "%REPO_URL%"=="" (
    echo [LOI] Ban chua nhap URL repository. Vui long chay lai script!
    pause
    exit /b 1
)

echo.
echo Dang kiem tra va lien ket Remote Origin...
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%

echo.
echo Dang day code len GitHub (nhanh main)...
git branch -M main
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo [THANH CONG] Da day toan bo ma nguon len GitHub thanh cong!
    echo.
    echo Bay gio ban chi can:
    echo 1. Vao Render: https://dashboard.render.com/select-repo?type=web
    echo 2. Chon repository ban vua day len.
    echo 3. Render se tu dong nạp cau hinh render.yaml co san!
    echo ======================================================================
    start https://dashboard.render.com/select-repo?type=web
) else (
    echo.
    echo ======================================================================
    echo [CHU Y] Neu GitHub yeu cau xac thuc:
    echo - Hay dang nhap Personal Access Token hoac GitHub Desktop.
    echo ======================================================================
)

echo.
pause
