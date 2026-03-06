import os
import json

class ToolCall:
    def __init__(self, name, args, id=None):
        self.name = name
        self.args = args
        self.id = id

class LLMResponse:
    def __init__(self, text=None, function_calls=None):
        self.text = text
        self.function_calls = function_calls or []

class GeminiChatSession:
    def __init__(self, model, system_instruction, tools, temperature, mcp_tools=None):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError("Please install google-genai package.")
        
        self.types = types
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        client = genai.Client(api_key=api_key)
        
        all_tools = list(tools) if tools else []
        if mcp_tools:
            for mt in mcp_tools:
                fun_desc = mt["function"]
                fd = types.FunctionDeclaration(
                    name=fun_desc["name"],
                    description=fun_desc.get("description", ""),
                    parameters=fun_desc.get("parameters", {})
                )
                all_tools.append(types.Tool(function_declarations=[fd]))
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=all_tools,
            temperature=temperature,
        )
        self.chat = client.chats.create(model=model, config=config)
        
    def _parse_response(self, response):
        calls = []
        if response.function_calls:
            for fc in response.function_calls:
                calls.append(ToolCall(name=fc.name, args={k: v for k,v in fc.args.items()}))
        return LLMResponse(text=response.text, function_calls=calls)

    def send_message(self, message):
        response = self.chat.send_message(message)
        return self._parse_response(response)
        
    def send_tool_results(self, tool_results):
        parts = []
        for res in tool_results:
            parts.append(self.types.Part.from_function_response(
                name=res["name"],
                response={"result": res["result"]}
            ))
        response = self.chat.send_message(parts)
        return self._parse_response(response)

class OpenAIChatSession:
    def __init__(self, model, system_instruction, tools, temperature, base_url, api_key, mcp_tools=None):
        try:
            import openai
        except ImportError:
            raise ImportError("Please run 'pip install openai' to use KIMI or DeepSeek.")
        
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        # For local models, strongly encourage tool use in the system prompt
        enhanced_instruction = (
            f"{system_instruction}\n"
            "CRITICAL: You are running locally and HAVE permissions to access the file system, execute commands, and fetch real-time data. "
            "You MUST use the provided tools to fulfill user requests involving the local system, precise time, or weather. "
            "NEVER say you cannot access the file system or internet. Use the tools."
        )
        
        self.messages = [
            {"role": "system", "content": enhanced_instruction}
        ]
        
        self.tools = []
        if tools:
            for tool in tools:
                import inspect
                sig = inspect.signature(tool)
                props = {}
                required = []
                for name, param in sig.parameters.items():
                    props[name] = {"type": "string"}
                    required.append(name)
                
                desc = tool.__doc__
                if not desc:
                    if tool.__name__ == "read_file":
                        desc = "Reads a file using its absolute path."
                    elif tool.__name__ == "list_directory":
                        desc = "Lists all files and folders inside a given absolute directory path."
                    elif tool.__name__ == "get_current_time":
                        desc = "Gets the current local date and time."
                    elif tool.__name__ == "get_weather":
                        desc = "Gets the current weather for a specified city (e.g. 'Beijing', 'New York')."
                    elif tool.__name__ in ("write_file", "write_file_sync"):
                        desc = "Writes to/modifies a file given its filepath and the content."
                    elif tool.__name__ in ("execute_command", "execute_command_sync"):
                        desc = "Executes Windows Shell commands."
                    else:
                        desc = f"Call {tool.__name__}"
                
                self.tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.__name__,
                        "description": desc,
                        "parameters": {
                            "type": "object",
                            "properties": props,
                            "required": required
                        }
                    }
                })

        if mcp_tools:
            for mt in mcp_tools:
                self.tools.append(mt)

    def _parse_response(self, response):
        msg = response.choices[0].message
        
        msg_dict = {
            "role": msg.role,
            "content": msg.content or "",
        }
        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                tc_dict = {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                tool_calls.append(tc_dict)
            msg_dict["tool_calls"] = tool_calls
            
        self.messages.append(msg_dict)
        
        text = msg.content
        calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                args = {}
                if tc.function.arguments:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        pass
                calls.append(ToolCall(name=tc.function.name, args=args, id=tc.id))
        elif msg.content:
            # Fallback for models (like some local Ollama models) that output function calls as raw JSON text embedded in their response
            import re
            
            # Find all JSON-like structures that look like tool calls: {"name": "...", "arguments": {...}}
            json_matches = re.finditer(r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\}', msg.content, re.DOTALL)
            
            for match in json_matches:
                json_str = match.group(0)
                try:
                    content_json = json.loads(json_str)
                    if isinstance(content_json, dict) and "name" in content_json and "arguments" in content_json:
                        import uuid
                        fake_id = "call_" + str(uuid.uuid4())[:8]
                        calls.append(ToolCall(name=content_json["name"], args=content_json["arguments"], id=fake_id))
                        
                        # Also append it to the message dict so history remains consistent
                        if "tool_calls" not in msg_dict:
                            msg_dict["tool_calls"] = []
                            
                        msg_dict["tool_calls"].append({
                            "id": fake_id,
                            "type": "function",
                            "function": {
                                "name": content_json["name"],
                                "arguments": json.dumps(content_json["arguments"])
                            }
                        })
                        # Remove the JSON text from the content so we don't display raw UI JSON
                        msg_dict["content"] = msg_dict["content"].replace(json_str, "")
                        text = (text or "").replace(json_str, "")
                except json.JSONDecodeError:
                    continue
        return LLMResponse(text=text, function_calls=calls)

    def send_message(self, message):
        self.messages.append({"role": "user", "content": message})
        kwargs = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
        }
        if self.tools:
            kwargs["tools"] = self.tools
            
        response = self.client.chat.completions.create(**kwargs)
        return self._parse_response(response)

    def send_tool_results(self, tool_results):
        for res in tool_results:
            self.messages.append({
                "role": "tool",
                "tool_call_id": res["id"],
                "content": str(res["result"])
            })
            
        kwargs = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
        }
        if self.tools:
            kwargs["tools"] = self.tools
            
        response = self.client.chat.completions.create(**kwargs)
        return self._parse_response(response)

def create_chat_session(system_instruction, tools, mcp_tools=None):
    # Enforce Chinese output globally for all providers
    system_instruction += "\nIMPORTANT: You MUST respond to the user exclusively in Chinese (简体中文). All your explanations, thoughts, and conversational text must be in Chinese."

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    temperature = 0.0
    
    if provider == "gemini":
        model = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")
        return GeminiChatSession(model, system_instruction, tools, temperature, mcp_tools)
    elif provider == "kimi":
        model = os.environ.get("LLM_MODEL", "moonshot-v1-8k")
        api_key = os.environ.get("KIMI_API_KEY")
        if not api_key:
            raise ValueError("KIMI_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.moonshot.cn/v1", api_key, mcp_tools)
    elif provider == "deepseek":
        model = os.environ.get("LLM_MODEL", "deepseek-chat")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.deepseek.com", api_key, mcp_tools)
    elif provider == "ollama":
        model = os.environ.get("LLM_MODEL", "qwen2.5:3b")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "http://localhost:11434/v1", "ollama", mcp_tools)
    else:
        raise ValueError(f"Unknown LLM Provider: {provider}")
