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
    def __init__(self, model, system_instruction, tools, temperature, history=None, mcp_tools=None):
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
        
        # Format history for Gemini if provided
        gemini_history = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                ))
        
        self.chat = client.chats.create(model=model, config=config, history=gemini_history)
        
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
    def __init__(self, model, system_instruction, tools, temperature, base_url, api_key, history=None, mcp_tools=None):
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
            "You MUST use the provided tools to fulfill user requests involving the local system, precise time, your location, or weather. "
            "NEVER say you cannot access the file system, internet, or geolocation. Use the tools."
        )
        
        self.messages = [
            {"role": "system", "content": enhanced_instruction}
        ]
        
        # Inject history if provided
        if history:
            for msg in history:
                # OpenAI map roles exactly (user -> user, model/agent -> assistant)
                role = "user" if msg["role"] == "user" else "assistant"
                self.messages.append({"role": role, "content": msg["content"]})
        
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
            "content": msg.content if msg.content is not None else "",
        }
        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                tc_dict = {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments)
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
            
            # Also catch standard codeblocks ` ` `json { "name": "...", "arguments": {...} } ` ` `
            codeblock_matches = re.finditer(r'```(?:json)?\s*(\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\})\s*```', msg.content, re.DOTALL)
            
            all_json_strings = [m.group(0) for m in json_matches] + [m.group(1) for m in codeblock_matches]
            # Remove duplicates safely
            all_json_strings = list(dict.fromkeys(all_json_strings))
            
            for json_str in all_json_strings:
                try:
                    content_json = json.loads(json_str)
                    if isinstance(content_json, dict) and "name" in content_json and "arguments" in content_json:
                        import uuid
                        fake_id = "call_" + str(uuid.uuid4())[:8]
                        # Handle case where arguments is given as a string instead of dict
                        args = content_json["arguments"]
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                pass
                                
                        calls.append(ToolCall(name=content_json["name"], args=args, id=fake_id))
                        
                        # Also append it to the message dict so history remains consistent
                        if "tool_calls" not in msg_dict:
                            msg_dict["tool_calls"] = []
                            
                        msg_dict["tool_calls"].append({
                            "id": fake_id,
                            "type": "function",
                            "function": {
                                "name": content_json["name"],
                                "arguments": json.dumps(args)
                            }
                        })
                        # Remove the JSON text from the content so we don't display raw UI JSON
                        msg_dict["content"] = msg_dict["content"].replace(json_str, "")
                        text = (text or "").replace(json_str, "")
                        
                        # also strip codeblocks if we matched them via codeblock
                        text = re.sub(r'```(?:json)?\s*```', '', text)
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
                "name": res["name"],
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

class AnthropicChatSession:
    def __init__(self, model, system_instruction, tools, temperature, api_key, history=None, mcp_tools=None):
        try:
            import anthropic
        except ImportError:
            raise ImportError("Please run 'pip install anthropic' to use Claude.")
            
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.system = system_instruction
        self.temperature = temperature
        
        self.messages = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "assistant"
                self.messages.append({"role": role, "content": msg["content"]})
                
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
                
                desc = tool.__doc__ or f"Call {tool.__name__}"
                
                self.tools.append({
                    "name": tool.__name__,
                    "description": desc,
                    "input_schema": {
                        "type": "object",
                        "properties": props,
                        "required": required
                    }
                })

        # Process MCP Tools (convert OpenAI format to Anthropic format)
        if mcp_tools:
            for mt in mcp_tools:
                anthropic_tool = {
                    "name": mt["function"]["name"],
                    "description": mt["function"].get("description", ""),
                    "input_schema": mt["function"].get("parameters", {"type": "object", "properties": {}})
                }
                self.tools.append(anthropic_tool)

    def _parse_response(self, response):
        text = ""
        calls = []
        
        # Anthropic returns a list of blocks
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                calls.append(ToolCall(name=block.name, args=block.input, id=block.id))
                
        # Append the assistant's message correctly for Anthropic multi-turn
        self.messages.append({"role": "assistant", "content": response.content})
        
        return LLMResponse(text=text.strip(), function_calls=calls)

    def send_message(self, message):
        self.messages.append({"role": "user", "content": message})
        
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "system": self.system,
            "messages": self.messages,
            "temperature": self.temperature,
        }
        if self.tools:
            kwargs["tools"] = self.tools
            
        response = self.client.messages.create(**kwargs)
        return self._parse_response(response)

    def send_tool_results(self, tool_results):
        # Anthropic expects tool results as a user message containing generic block schemas
        tool_content_blocks = []
        for res in tool_results:
            tool_content_blocks.append({
                "type": "tool_result",
                "tool_use_id": res["id"],
                "content": str(res["result"])
            })
            
        self.messages.append({
            "role": "user",
            "content": tool_content_blocks
        })
        
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "system": self.system,
            "messages": self.messages,
            "temperature": self.temperature,
        }
        if self.tools:
            kwargs["tools"] = self.tools
            
        response = self.client.messages.create(**kwargs)
        return self._parse_response(response)

def create_chat_session(system_instruction, tools, history=None, mcp_tools=None):
    # Enforce Chinese output globally for all providers
    system_instruction += "\nIMPORTANT: You MUST respond to the user exclusively in Chinese (简体中文). All your explanations, thoughts, and conversational text must be in Chinese."

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    temperature = 0.0
    
    if provider == "gemini":
        model = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")
        return GeminiChatSession(model, system_instruction, tools, temperature, history=history, mcp_tools=mcp_tools)
    elif provider == "kimi":
        model = os.environ.get("LLM_MODEL", "moonshot-v1-8k")
        api_key = os.environ.get("KIMI_API_KEY")
        if not api_key:
            raise ValueError("KIMI_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.moonshot.cn/v1", api_key, history=history, mcp_tools=mcp_tools)
    elif provider == "deepseek":
        model = os.environ.get("LLM_MODEL", "deepseek-chat")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.deepseek.com", api_key, history=history, mcp_tools=mcp_tools)
    elif provider == "anthropic":
        model = os.environ.get("LLM_MODEL", "claude-3-5-sonnet-latest")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key: raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
        return AnthropicChatSession(model, system_instruction, tools, temperature, api_key, history=history, mcp_tools=mcp_tools)

    elif provider == "openai":
        model = os.environ.get("LLM_MODEL", "gpt-4o")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: raise ValueError("OPENAI_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.openai.com/v1", api_key, history=history, mcp_tools=mcp_tools)
    
    elif provider == "qwen":
        model = os.environ.get("LLM_MODEL", "qwen-plus")
        api_key = os.environ.get("QWEN_API_KEY")
        if not api_key: raise ValueError("QWEN_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://dashscope.aliyuncs.com/compatible-mode/v1", api_key, history=history, mcp_tools=mcp_tools)
        
    elif provider == "doubao":
        model = os.environ.get("LLM_MODEL", "doubao-pro-128k")
        api_key = os.environ.get("DOUBAO_API_KEY")
        if not api_key: raise ValueError("DOUBAO_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://ark.cn-beijing.volces.com/api/v3", api_key, history=history, mcp_tools=mcp_tools)

    elif provider == "zhipu":
        model = os.environ.get("LLM_MODEL", "glm-4-plus")
        api_key = os.environ.get("ZHIPU_API_KEY")
        if not api_key: raise ValueError("ZHIPU_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://open.bigmodel.cn/api/paas/v4/", api_key, history=history, mcp_tools=mcp_tools)

    elif provider == "baidu":
        model = os.environ.get("LLM_MODEL", "ernie-4.0-8k-latest")
        api_key = os.environ.get("BAIDU_API_KEY")
        if not api_key: raise ValueError("BAIDU_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://qianfan.baidubce.com/v2", api_key, history=history, mcp_tools=mcp_tools)

    elif provider == "01ai":
        model = os.environ.get("LLM_MODEL", "yi-lightning")
        api_key = os.environ.get("YI_API_KEY")
        if not api_key: raise ValueError("YI_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.lingyiwanwu.com/v1", api_key, history=history, mcp_tools=mcp_tools)

    elif provider == "siliconflow":
        model = os.environ.get("LLM_MODEL", "deepseek-ai/DeepSeek-V3")
        api_key = os.environ.get("SILICONFLOW_API_KEY")
        if not api_key: raise ValueError("SILICONFLOW_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.siliconflow.cn/v1", api_key, history=history, mcp_tools=mcp_tools)

    elif provider == "groq":
        model = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key: raise ValueError("GROQ_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.groq.com/openai/v1", api_key, history=history, mcp_tools=mcp_tools)

    elif provider == "ollama":
        model = os.environ.get("LLM_MODEL", "qwen2.5-coder:14b")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "http://localhost:11434/v1", "ollama", history=history, mcp_tools=mcp_tools)
        
    else:
        raise ValueError(f"Unknown LLM Provider: {provider}")
