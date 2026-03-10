@echo off
echo ==============================================
echo        Starting ClawYu Local AI Agent...
echo ==============================================
:: Set your LLM Provider.
:: Built-in Universal Options:
::  - gemini         (Google: gemini-2.5-flash-lite)
::  - openai         (OpenAI: gpt-4o / gpt-4o-mini)
::  - anthropic      (Anthropic: claude-3-5-sonnet-latest)
::  - qwen           (Aliyun: qwen-max / qwen-plus)
::  - doubao         (Volcengine: doubao-pro-128k)
::  - zhipu          (ZhipuAI: glm-4-plus)
::  - baidu          (Qianfan: ernie-4.0-8k-latest)
::  - 01ai           (01.AI: yi-lightning)
::  - deepseek       (DeepSeek: deepseek-chat)
::  - kimi           (Moonshot: moonshot-v1-8k)
::  - siliconflow    (SiliconFlow: e.g. deepseek-ai/DeepSeek-V3)
::  - groq           (Groq: llama-3.3-70b-versatile)
::  - ollama         (Local: qwen2.5-coder:14b) -> No API Key Needed
set LLM_PROVIDER=ollama
set LLM_MODEL=qwen2.5-coder:14b

:: ==============================================
:: API Keys (Fill the one you are going to use)
:: ==============================================
set GEMINI_API_KEY=your_gemini_api_key_here
set OPENAI_API_KEY=your_openai_api_key_here
set ANTHROPIC_API_KEY=your_anthropic_api_key_here
set QWEN_API_KEY=your_dashscope_api_key_here
set DOUBAO_API_KEY=your_volcengine_api_key_here
set ZHIPU_API_KEY=your_zhipu_api_key_here
set BAIDU_API_KEY=your_qianfan_api_key_here
set YI_API_KEY=your_01ai_api_key_here
set DEEPSEEK_API_KEY=your_deepseek_api_key_here
set KIMI_API_KEY=your_kimi_api_key_here
set SILICONFLOW_API_KEY=your_siliconflow_api_key_here
set GROQ_API_KEY=your_groq_api_key_here

timeout /t 1 /nobreak >nul

start http://127.0.0.1:8000

G:\anaconda\python.exe clawyu_server.py
