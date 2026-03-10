# ClawYu Local AI Agent 🐾

ClawYu is a powerful, privacy-first local AI assistant designed to act as your ultimate pair-programming and system administration companion.

Unlike standard cloud-based chatbots, ClawYu is granted **permissions to interact with your local Windows system** and **browse the live internet**. Powered by an asynchronous core and a dynamic plugin architecture, ClawYu seamlessly executes complex tasks—from scraping web data to refactoring giant codebases—all from a beautifully crafted local Web GUI.

## ✨ Key Features

* **Elegant, Premium Web UI Workspace**
  * Experience an immersive, glassmorphism-inspired UI with smooth animations.
  * Robust Markdown rendering with syntax highlighting and dedicated anti-overflow horizontal scrollbars for large code blocks and data tables.
  * Asynchronous status indicators (e.g., `"running tool 'read_web_page' (this might take a while)..."`) so the UI never freezes during heavy background tasks.

* **Dynamic Plugin Ecosystem**
  * ClawYu's capabilities are split into modular Python files inside the `plugins/` directory.
  * Writing a new capability for the AI is as simple as defining a standard Python function and inheriting from `PluginInterface`.
  * **Built-in Plugins** include Local File System management, Windows Shell execution, Geolocation, and Weather fetching.

* **Autonomous Web Browsing & Search**
  * Integrated with **Playwright**, ClawYu can fetch live data from the web.
  * Can autonomously search for current events (via Bing to ensure connectivity) and scrape deep text from complex HTML webpages into its context.

* **Persistent SQLite Memory**
  * Built-in `memory_manager.py` backed by SQLite tracks all your conversations and tool execution results permanently. ClawYu remembers what you did last time.

* **Strict Security & Authorization**
  * Because the Agent has authority to modify the local system, all write (`write_file`) and execute (`execute_command`) operations trigger **mandatory visual confirmation prompts**. ClawYu cannot modify your disks without you explicitly clicking "Approve".

* **Universal LLM Flexibility**
  * Seamlessly switch between online giants (**Google Gemini**, **DeepSeek**, **Moonshot/Kimi**) and fully offline local models (**Ollama** like Qwen, Llama).
  * Highly tuned prompt engineering ensures local models strictly utilize provided tools.

* **🪐 Native MCP (Model Context Protocol) Support**
  * ClawYu dynamically supports Anthropic's open MCP standard. By writing a simple `mcp_config.json`, ClawYu can connect to thousands of active MCP servers (SQL Databases, GitHub, Slack, etc.).

## 🚀 Quick Start

This project requires a Python/Anaconda environment.

### 1. Prerequisites

Ensure you have the necessary dependencies installed:

```bash
pip install fastapi uvicorn websockets rich
pip install google-genai openai
pip install playwright beautifulsoup4
```

**Important:** To enable the AI's Web Browsing eyes, you must install the headless browser component:

```bash
playwright install chromium
```

### 2. Configure Your LLM Provider

ClawYu now uses a universal Multi-LLM architecture. Open `start_clawyu.bat` to configure your ultimate brain:

* **For Local Ollama (Free & Private - Recommended for developers):**
  1. Install [Ollama](https://ollama.com/) and run `ollama pull qwen2.5-coder:14b` (or your preferred model).
  2. Set `LLM_PROVIDER=ollama` and `LLM_MODEL=qwen2.5-coder:14b` in `start_clawyu.bat`.
* **Universal Cloud Providers:**
  Simply change `LLM_PROVIDER` in `start_clawyu.bat` and fill in the corresponding `API_KEY` below it.
  * `openai`: GPT-4o, GPT-4o-mini
  * `anthropic`: Claude 3.5 Sonnet
  * `gemini`: Gemini 2.5 Flash / Pro
  * `qwen`: Aliyun Qwen-Max / Qwen-Plus
  * `doubao`: Volcengine Doubao-Pro-128k
  * `zhipu`: ZhipuAI GLM-4-Plus
  * `baidu`: Qianfan Ernie 4.0
  * `01ai`: Yi-Lightning
  * `deepseek`: DeepSeek-Chat (V3) / Reasoner (R1)
  * `kimi`: Moonshot-v1-8k
  * `siliconflow`: SiliconFlow endpoints
  * `groq`: Llama-3.3-70b-versatile via Groq

### 3. One-Click Startup

1. Edit the `start_clawyu.bat` file in the root directory to match your API keys and provider.
2. **Double-click `start_clawyu.bat` to run it!**

The script will automatically spin up the FastAPI server, initialize the SQLite database, preload all plugins, and open `http://127.0.0.1:8000` in your default browser.

## 🛠️ Built-in Tools Architecture

ClawYu's `plugins/` directory exposes the following toolsets to the AI:

### `system_tools.py`

* `list_directory(directory_path)`: Scans folder hierarchies.
* `read_file(filepath)`: Ingests documents and source code.
* `write_file_sync(filepath, content)`: Modifies code and writes files *(Requires GUI User Approval)*.
* `execute_command_sync(command)`: Executes terminal scripts *(Requires GUI User Approval)*.

### `browser_tools.py`

* `search_web(query)`: Uses live search engines to find recent links.
* `read_web_page(url)`: Deploys a headless Chromium instance to extract deep text from dynamic URLs.

### `web_tools.py`

* `get_current_time()`: Local system time standardizer.
* `get_my_location()`: IPv4 based geolocation.
* `get_weather(city)`: Fetches precise meteorological data via Open-Meteo API.

## 🔌 Model Context Protocol (MCP) Extensions

To bridge ClawYu into existing enterprise datasets, edit `mcp_config.json`:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "test.db"]
    }
  }
}
```

Start ClawYu as usual. It automatically translates the MCP protocol feeds directly into the AI's functional tool belt!

---
**ClawYu - Your Omnipotent Local AI Pair Programming Assistant!** 🐾🚀
