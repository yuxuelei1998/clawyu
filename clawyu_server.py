import os
import sys
import json
import asyncio
import subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from llm_provider import create_chat_session

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
pending_authorizations = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

async def request_authorization(websocket: WebSocket, action: str, details: str) -> bool:
    auth_id = os.urandom(8).hex()
    event = asyncio.Event()
    pending_authorizations[auth_id] = {
        "event": event,
        "approved": False
    }
    
    await websocket.send_text(json.dumps({
        "type": "auth_request",
        "auth_id": auth_id,
        "action": action,
        "details": details
    }))
    
    await event.wait()
    
    approved = pending_authorizations[auth_id]["approved"]
    del pending_authorizations[auth_id]
    return approved

def read_file(filepath: str) -> str:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {filepath}: {e}"

def write_file_sync(filepath: str, content: str) -> str:
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"File {filepath} written successfully."
    except Exception as e:
        return f"Error writing file {filepath}: {e}"

def execute_command_sync(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        output = f"Exit code: {result.returncode}\n"
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        return output
    except Exception as e:
        return f"Error executing command: {e}"

# LLM client initialization handled in create_chat_session

async def process_chat(websocket: WebSocket, chat, user_msg: str):
    try:
        await manager.send_message(json.dumps({"type": "status", "content": "thinking"}), websocket)

        response = await asyncio.to_thread(chat.send_message, user_msg)
        
        while response.function_calls:
            tool_results = []
            for function_call in response.function_calls:
                name = function_call.name
                args = function_call.args
                
                await manager.send_message(json.dumps({"type": "status", "content": f"running tool '{name}'..."}), websocket)
                
                if name == "read_file":
                    result = await asyncio.to_thread(read_file, **args)
                
                elif name == "list_directory":
                    dir_path = args.get("dir_path", "Unknown")
                    try:
                        files = await asyncio.to_thread(os.listdir, dir_path)
                        result = f"Contents of {dir_path}:\n" + "\n".join(files)
                    except Exception as e:
                        result = f"Error listing directory {dir_path}: {e}"
                        
                elif name == "get_current_time":
                    from datetime import datetime
                    result = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                elif name == "get_weather":
                    city = args.get("city", "")
                    def fetch_weather(c):
                        import urllib.request
                        import urllib.parse
                        import ssl
                        try:
                            url = f"https://wttr.in/{urllib.parse.quote(c)}?format=3"
                            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                            ctx = ssl.create_default_context()
                            ctx.check_hostname = False
                            ctx.verify_mode = ssl.CERT_NONE
                            with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
                                return response.read().decode('utf-8').strip()
                        except Exception as e:
                            return f"Error fetching weather for {c}: {e}"
                    result = await asyncio.to_thread(fetch_weather, city)
                        
                elif name == "write_file_sync":
                    filepath = args.get("filepath", "Unknown")
                    content = args.get("content", "")
                    preview = content[:300] + "..." if len(content) > 300 else content
                    details = f"File: {filepath}\n\nPreview:\n{preview}"
                    
                    approved = await request_authorization(websocket, "Write File", details)
                    if approved:
                        await manager.send_message(json.dumps({"type": "status", "content": f"writing to {filepath}..."}), websocket)
                        result = await asyncio.to_thread(write_file_sync, filepath, content)
                    else:
                        result = "Operation cancelled by user via GUI."
                        
                elif name == "execute_command_sync":
                    command = args.get("command", "")
                    details = f"Command:\n{command}"
                    
                    approved = await request_authorization(websocket, "Execute Command", details)
                    if approved:
                        await manager.send_message(json.dumps({"type": "status", "content": "executing command..."}), websocket)
                        result = await asyncio.to_thread(execute_command_sync, command)
                    else:
                        result = "Operation cancelled by user via GUI."
                else:
                    result = f"Tool {name} not found."
                    
                tool_results.append({
                    "id": getattr(function_call, "id", None),
                    "name": name,
                    "result": result
                })

            await manager.send_message(json.dumps({"type": "status", "content": "analyzing results..."}), websocket)
            response = await asyncio.to_thread(chat.send_tool_results, tool_results)

        if response.text:
            await manager.send_message(json.dumps({
                "type": "message",
                "role": "agent",
                "content": response.text
            }), websocket)
        
        await manager.send_message(json.dumps({"type": "status", "content": "idle"}), websocket)
    except Exception as e:
        await manager.send_message(json.dumps({
            "type": "error",
            "content": f"Error during chat processing: {str(e)}"
        }), websocket)
        await manager.send_message(json.dumps({"type": "status", "content": "idle"}), websocket)

@app.get("/")
async def get():
    with open("static/index.html", "r", encoding='utf-8') as f:
        html_content = f.read()
    return HTMLResponse(html_content)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    system_instruction=(
        "You are ClawYu, a highly capable local AI agent with a beautiful secure web GUI interface. "
        "You have access to the user's local system through function calling. You can read files, write files, and execute shell commands. "
        "You run on Windows. When you need to do something on the user's local system, USE THE TOOLS. "
        "IMPORTANT: You have tools to get the current time (`get_current_time`) and weather (`get_weather`). If the user asks for time or weather, you MUST use these tools. NEVER say you cannot access real-time info. "
        "Don't just give the user instructions to do it themselves unless you cannot do it or the user explicitly asks how to do it. "
        "All write and execute operations will prompt the user for confirmation securely via the GUI, so you don't need to ask for permission. "
        "Be helpful, concise, and proactive. When executing commands, remember the OS is Windows (Powershell/CMD)."
        "Since your interface is now a modern browser GUI, feel free to use standard markdown syntax (like **bold**, `code snippets`, URLs, and bullet points) in your replies, the frontend will render them beautifully."
    )
    
    def list_directory(dir_path: str) -> str:
        """Lists the contents of a directory using its absolute path."""
        pass
        
    def get_current_time() -> str:
        """Gets the current local date and time."""
        pass

    def get_weather(city: str) -> str:
        """Gets the current weather for a specified city."""
        pass

    tools = [read_file, write_file_sync, execute_command_sync, list_directory, get_current_time, get_weather]
    
    try:
        chat = create_chat_session(system_instruction, tools)
    except Exception as e:
        await manager.send_message(json.dumps({"type": "error", "content": f"Failed to initialize LLM Provider: {str(e)}\n\n(If you switched to Kimi or Deepseek, make sure you ran pip install openai)"}), websocket)
        return

    await manager.send_message(json.dumps({
        "type": "message", 
        "role": "agent", 
        "content": "✨ Welcome to the **ClawYu** Interface. I am connected and ready. What can I do for you today?"
    }), websocket)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if payload["type"] == "chat":
                user_msg = payload["content"]
                asyncio.create_task(process_chat(websocket, chat, user_msg))

            elif payload["type"] == "auth_response":
                auth_id = payload["auth_id"]
                approved = payload["approved"]
                if auth_id in pending_authorizations:
                    pending_authorizations[auth_id]["approved"] = approved
                    pending_authorizations[auth_id]["event"].set()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WS Error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("clawyu_server:app", host="127.0.0.1", port=8000, reload=True)
