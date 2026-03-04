# ClawYu Local AI Agent 🐾

ClawYu is a powerful local AI agent driven by the Google Gemini series (currently defaulting to `gemini-2.0-flash`).

Unlike standard cloud-based chat bots, ClawYu is granted **permissions to interact with your local system**. Based on your natural language instructions, it can intelligently read files, write code, edit documents, and even execute shell scripts on your Windows system to automate a wide variety of tasks.

## ✨ Key Features

* **Dual Interaction Interfaces**:
  * **Elegant Web UI Workspace**: Experience an immersive, modern UI design with support for Markdown rendering and code syntax highlighting, providing an exceptionally smooth user experience.
  * **CMD Terminal Mode**: Seamlessly interact via the pure text terminal.
* **Strict Security & Authorization Mechanism**: Because the Agent has the authority to modify the local system, all write (`write_file`) and execute (`execute_command`) operations trigger **mandatory visual confirmation prompts for user review**. You can preview the code to be written or the command to be executed, and they will only take effect after you explicitly click "Approve", ensuring 100% system security.
* **Powerful Local Execution**:
  * Easily read and analyze massive local codebases.
  * Automatically create files and refactor code for you.
  * Execute PowerShell commands to search for information, scrape the web, or manage the file system in the background.
* **Free and Capable**: Switched to and optimized for the `gemini-2.0-flash` model API, enjoying an extremely high free-tier quota (1500 requests per day), more than enough to handle high-intensity local development and collaboration.

## 🚀 Quick Start

This project requires an Anaconda/Python environment along with the latest `google-genai` and `fastapi` frameworks.

### 1. Prerequisites

Ensure you have the necessary dependencies installed (preferably within your Anaconda environment):

```bash
pip install fastapi uvicorn websockets google-genai rich
```

### 2. Obtain an API Key

Since ClawYu's "brain" relies on Google Gemini, please visit [Google AI Studio](https://aistudio.google.com/) to apply for your **free API Key**, and have it ready to be injected into the startup script.

### 3. One-Click Startup (Recommended Web UI)

We provide an extremely convenient auto-launch script for you.

1. Open the `start_clawyu.bat` file in the root directory (you can right-click and edit it).
2. Replace the placeholder content after `GEMINI_API_KEY=` on line 3 with your actual API Key.
3. **Double-click `start_clawyu.bat` to run it!**

The script will automatically spin up the FastAPI server in the background and **automatically launch your default web browser** to open `http://127.0.0.1:8000`, landing you straight into the ClawYu system!

### 4. Terminal Command Line Startup (Fallback)

If you prefer to solely use the black-box terminal:

```bash
# 1. Set the temporary environment variable in the terminal
set GEMINI_API_KEY=YOUR_API_KEY

# 2. Start the pure command-line version of ClawYu
python clawyu.py
```

## 🛠️ Built-in Tools

ClawYu exposes the following local Python functions internally to the LLM:
* `read_file(filepath)`: Reads a file using its absolute path.
* `write_file_sync(filepath, content)`: Writes to/modifies a file (Subject to strict security review).
* `execute_command_sync(command)`: Executes Windows Shell commands (Subject to strict security review).

*Note: Currently, due to the limitations of the Google GenAI SDK v1beta version, official built-in tools (such as Google Search) cannot be combined with custom functions (Function Calling). Therefore, the Agent autonomously writes scripts to perform web searches when necessary.*

---
**ClawYu - Your Omnipotent Local AI Pair Programming Assistant!** 💻🚀
