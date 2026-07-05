@echo off
cd /d "%~dp0"
echo Starting WC Oracle API on http://localhost:8000 ...
"C:\Users\abhin\mini\envs\fifa_wc\python.exe" -m uvicorn api.main:app --reload --port 8000
pause
