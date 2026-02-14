@echo off
cd /d %~dp0
call venv\Scripts\activate
start http://localhost:8000
uvicorn main:app --host 0.0.0.0 --port 8000
pause
