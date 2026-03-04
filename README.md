# ClawYu Local AI Agent

`ClawYu` is a powerful, local AI agent (inspired by tools like OpenInterpreter) that brings the reasoning power of Gemini directly to your local machine. It can read files, write code, and execute shell commands to automatically accomplish tasks on your behalf.

**Security First**: It features a strict "Human-in-the-loop" security model. Any time the agent wants to write a file or execute a command, it will pause and ask for your explicit `(y/n)` permission.

## Setup Instructions

### 1. Install Dependencies

Make sure you have Python installed. Then, install the required packages:

```bash
pip install -r requirements.txt
```

### 2. Get Your Gemini API Key

To act as the "brain", ClawYu needs a Gemini API key.

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Sign in with your Google account (your Gemini Advanced/Premium account will work).
3. Click on the **"Create API key"** button.
4. Copy the generated API key.

### 3. Set the Environment Variable

You must set your API key as an environment variable named `GEMINI_API_KEY`.

**On Windows (Command Prompt):**

```cmd
set GEMINI_API_KEY=your_api_key_here
```

**On Windows (PowerShell):**

```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

*(Note: To set it permanently on Windows, search for "Environment Variables" in your Start Menu and add it to your User variables.)*

### 4. Run `ClawYu`

Start the agent by running:

```bash
python clawyu.py
```

## Usage Example

Once running, simply type your request in natural language:

- *"List all the files in this folder."*
- *"Create a new Python script that prints 'Hello World' and run it."*
- *"Find all the .txt files in my Documents folder and summarize them."*

The agent will figure out which tools to use and ALWAYS ask for permission before modifying your system.
