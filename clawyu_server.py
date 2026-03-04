import os
import sys
import json
import asyncio
import subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

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

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY environment variable not set.")
    sys.exit(1)

client = genai.Client(api_key=api_key)

@app.get("/")
async def get():
    with open("static/index.html", "r", encoding='utf-8') as f:
        html_content = f.read()
    return HTMLResponse(html_content)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are ClawYu, a highly capable local AI agent with a beautiful secure web GUI interface. "
            "You have access to the user's local system through function calling. You can read files, write files, and execute shell commands. "
            "You run on Windows. When you need to do something on the user's system, USE THE TOOLS. "
            "Don't just give the user instructions to do it themselves unless you cannot do it or the user explicitly asks how to do it. "
            "All write and execute operations will prompt the user for confirmation securely via the GUI, so you don't need to ask for permission. "
            "Be helpful, concise, and proactive. When executing commands, remember the OS is Windows (Powershell/CMD)."
            "Since your interface is now a modern browser GUI, feel free to use standard markdown syntax (like **bold**, `code snippets`, URLs, and bullet points) in your replies, the frontend will render them beautifully."
        ),
        tools=[read_file, write_file_sync, execute_command_sync], 
        temperature=0.0,
    )
    
    try:
        chat = client.chats.create(model="gemini-2.0-flash", config=config)
    except Exception as e:
        await manager.send_message(json.dumps({"type": "error", "content": f"Failed to initialize Gemini: {str(e)}"}), websocket)
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
                
                await manager.send_message(json.dumps({"type": "status", "content": "thinking"}), websocket)

                response = chat.send_message(user_msg)
                
                while response.function_calls:
                    tool_results = []
                    for function_call in response.function_calls:
                        name = function_call.name
                        args = function_call.args
                        
                        await manager.send_message(json.dumps({"type": "status", "content": f"running tool '{name}'..."}), websocket)
                        
                        if name == "read_file":
                            result = read_file(**args)
                        
                        elif name == "write_file_sync":
                            filepath = args.get("filepath", "Unknown")
                            content = args.get("content", "")
                            preview = content[:300] + "..." if len(content) > 300 else content
                            details = f"File: {filepath}\n\nPreview:\n{preview}"
                            
                            approved = await request_authorization(websocket, "Write File", details)
                            if approved:
                                await manager.send_message(json.dumps({"type": "status", "content": f"writing to {filepath}..."}), websocket)
                                result = write_file_sync(filepath, content)
                            else:
                                result = "Operation cancelled by user via GUI."
                                
                        elif name == "execute_command_sync":
                            command = args.get("command", "")
                            details = f"Command:\n{command}"
                            
                            approved = await request_authorization(websocket, "Execute Command", details)
                            if approved:
                                await manager.send_message(json.dumps({"type": "status", "content": "executing command..."}), websocket)
                                result = execute_command_sync(command)
                            else:
                                result = "Operation cancelled by user via GUI."
                        else:
                            result = f"Tool {name} not found."
                            
                        tool_results.append(types.Part.from_function_response(
                            name=name,
                            response={"result": result}
                        ))

                    await manager.send_message(json.dumps({"type": "status", "content": "analyzing results..."}), websocket)
                    response = chat.send_message(tool_results)

                if response.text:
                    await manager.send_message(json.dumps({
                        "type": "message",
                        "role": "agent",
                        "content": response.text
                    }), websocket)
                
                await manager.send_message(json.dumps({"type": "status", "content": "idle"}), websocket)

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
