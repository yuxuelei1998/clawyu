@echo off
echo ==============================================
echo        Starting ClawYu Local AI Agent...
echo ==============================================

set LLM_PROVIDER=gemini
set LLM_MODEL=gemini-2.5-flash-lite

:: Provider API Keys
set GEMINI_API_KEY=your_gemini_api_key_here
set KIMI_API_KEY=your_kimi_api_key_here
set DEEPSEEK_API_KEY=your_deepseek_api_key_here
timeout /t 1 /nobreak >nul

start http://127.0.0.1:8000

G:\anaconda\python.exe clawyu_server.py
