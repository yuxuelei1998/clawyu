@echo off
echo ==============================================
echo        Starting ClawYu Local AI Agent...
echo ==============================================

set GEMINI_API_KEY=

timeout /t 1 /nobreak >nul

start http://127.0.0.1:8000

G:\anaconda\python.exe clawyu_server.py
