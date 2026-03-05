@echo off
echo ==============================================
echo        Starting ClawYu Local AI Agent...
echo ==============================================
:: Set your LLM Provider. Built-in options: gemini, kimi, deepseek, ollama
:: If using ollama, make sure you have installed it and pulled the model (e.g., ollama pull qwen2.5:3b)
set LLM_PROVIDER=ollama
set LLM_MODEL=qwen2.5-coder:14b

:: Provider API Keys
set GEMINI_API_KEY=your_gemini_api_key_here
set KIMI_API_KEY=your_kimi_api_key_here
set DEEPSEEK_API_KEY=your_deepseek_api_key_here
timeout /t 1 /nobreak >nul

start http://127.0.0.1:8000

G:\anaconda\python.exe clawyu_server.py
