import os
import sys
import json
import asyncio
import subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from llm_provider import create_chat_session
from mcp_manager import mcp_manager
from plugin_manager import plugin_manager
from memory_manager import memory_manager

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
    pass # Migrated to plugin

def write_file_sync(filepath: str, content: str) -> str:
    pass # Migrated to plugin

def execute_command_sync(command: str) -> str:
    pass # Migrated to plugin

# LLM client initialization handled in create_chat_session

async def process_chat(websocket: WebSocket, chat, user_msg: str, session_id: str):
    try:
        # Save user message to memory
        await asyncio.to_thread(memory_manager.add_message, session_id, "user", user_msg)
        
        await manager.send_message(json.dumps({"type": "status", "content": "thinking"}), websocket)

        response = await asyncio.to_thread(chat.send_message, user_msg)
        
        while response.function_calls:
            tool_results = []
            for function_call in response.function_calls:
                name = function_call.name
                args = function_call.args
                
                await manager.send_message(json.dumps({"type": "status", "content": f"running tool '{name}'..."}), websocket)
                
                # Security checks for specific sensitive tools
                if name == "write_file_sync":
                    filepath = args.get("filepath", "Unknown")
                    content = args.get("content", "")
                    preview = content[:300] + "..." if len(content) > 300 else content
                    details = f"File: {filepath}\n\nPreview:\n{preview}"
                    
                    approved = await request_authorization(websocket, "Write File", details)
                    if not approved:
                        tool_results.append({
                            "id": getattr(function_call, "id", None),
                            "name": name,
                            "result": "Operation cancelled by user via GUI."
                        })
                        continue

                elif name == "execute_command_sync":
                    command = args.get("command", "")
                    details = f"Command:\n{command}"
                    
                    approved = await request_authorization(websocket, "Execute Command", details)
                    if not approved:
                        tool_results.append({
                            "id": getattr(function_call, "id", None),
                            "name": name,
                            "result": "Operation cancelled by user via GUI."
                        })
                        continue

                # Execute MCP tools
                if name.startswith("mcp_"):
                    parts = name.split("___", 1)
                    if len(parts) == 2:
                        server_name_part = parts[0][4:] # remove "mcp_"
                        mcp_tool_name = parts[1]
                        result = await mcp_manager.call_tool(server_name_part, mcp_tool_name, args)
                    else:
                        result = f"Invalid MCP tool name format: {name}"
                else:
                    # Execute dynamically loaded plugin tools
                    tool_func = next((t for t in plugin_manager.get_tools() if t.__name__ == name), None)
                    if tool_func:
                        try:
                            # Let the user know if it's a known slow tool
                            if name in ["read_web_page", "search_web"]:
                                await manager.send_message(json.dumps({"type": "status", "content": f"running tool '{name}' (this might take a while)..."}), websocket)
                                
                            result = await asyncio.to_thread(tool_func, **args)
                        except Exception as e:
                            result = f"Error executing tool {name}: {e}"
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
            # Save AI response to memory
            await asyncio.to_thread(memory_manager.add_message, session_id, "model", response.text)
            
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

@app.on_event("startup")
async def startup_event():
    await mcp_manager.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    await mcp_manager.close()

@app.get("/")
async def get():
    with open("static/index.html", "r", encoding='utf-8') as f:
        html_content = f.read()
    return HTMLResponse(html_content)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    system_instruction=(
        "你是 ClawYu，一个极其强大的本地 AI 智能体，拥有精美的安全 Web GUI 界面。\n"
        "你当前运行在用户的 Windows 系统上，并且**你已经连接到互联网**。\n"
        "你可以通过调用函数（Tools）来访问用户的本地系统、执行操作和获取实时网络数据。你可以读取文件、写入文件、执行 Shell 命令，并与 MCP 服务器交互。\n"
        "非常重要（CRITICAL）：你拥有获取当前时间（`get_current_time`）、获取物理位置（`get_my_location`）和获取天气（`get_weather`）的专属工具。当用户询问天气、时间或位置时，你**必须**调用这些工具！**绝对不准**回答你没有联网、无法获取位置或实时信息。\n"
        "当你在用户本地系统需要做什么时，直接使用工具！不要只给用户列出操作步骤让他们自己去执行，除非你真的做不到，或者用户明确要求你教他们怎么做。\n"
        "所有的写入和执行命令操作都会通过 GUI 安全地提示用户确认，因此你不需要在对话中重复请求用户的许可。\n"
        "你的回复应当有帮助、简洁且主动。由于你的界面是由现代浏览器渲染的，请在回复中自由使用标准 Markdown 语法（如 **加粗**、`代码片段`、链接和列表），前端会把它们渲染得很漂亮。\n\n"
        "对于复杂任务（例如构建项目、调研资料、编译代码），你需要化身为一个**自主智能体（AUTONOMOUS AGENT）**。\n"
        "将任务拆分为多个步骤，并在行动前进行逐步思考（Think step-by-step）。请连续使用工具。\n"
        "例如：'Thought: 我先检查一下当前目录。' -> 调用工具 -> 'Thought: 现在我将清理旧文件。' -> 调用工具 -> 'Thought: 现在我要写入新代码。' -> 调用工具。\n"
        "不要为了下一步的显而易见的操作而停下来询问用户许可；直接使用工具去干活系统会自动处理授权。"
    )
    
    # Load tools dynamically from plugins directory
    plugin_mgr_tools = plugin_manager.load_plugins()
    tools = plugin_mgr_tools
    mcp_tools = await mcp_manager.get_all_tools()
    
    session_id = "default_session" # For a single-user local agent, a fixed session is fine.
    
    # Fetch history
    history = await asyncio.to_thread(memory_manager.get_history, session_id)
    
    try:
        chat = create_chat_session(system_instruction, tools, history=history, mcp_tools=mcp_tools)
    except Exception as e:
        await manager.send_message(json.dumps({"type": "error", "content": f"Failed to initialize LLM Provider: {str(e)}\n\n(If you switched to Kimi or Deepseek, make sure you ran pip install openai)"}), websocket)
        return

    await manager.send_message(json.dumps({
        "type": "message", 
        "role": "agent", 
        "content": "✨ Welcome to the **ClawYu** Interface. I am connected and ready. (Conversation history loaded)"
    }), websocket)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if payload["type"] == "chat":
                user_msg = payload["content"]
                asyncio.create_task(process_chat(websocket, chat, user_msg, session_id))

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
