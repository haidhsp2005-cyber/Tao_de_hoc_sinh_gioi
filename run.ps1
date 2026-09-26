Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  OLYMPIAD PROBLEM FORGE - HỆ THỐNG TẠO ĐỀ THI HSG TIN HỌC" -ForegroundColor Yellow
Write-Host "  Chạy với Google Gemini 2.5 Flash API" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan

Start-Process "http://localhost:5000"
python server.py
