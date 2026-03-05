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
    def __init__(self, model, system_instruction, tools, temperature):
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
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools,
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
    def __init__(self, model, system_instruction, tools, temperature, base_url, api_key):
        try:
            import openai
        except ImportError:
            raise ImportError("Please run 'pip install openai' to use KIMI or DeepSeek.")
        
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        
        self.messages = [
            {"role": "system", "content": system_instruction}
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

    def _parse_response(self, response):
        msg = response.choices[0].message
        self.messages.append(msg)
        
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
                
        text = msg.content
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

def create_chat_session(system_instruction, tools):
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    temperature = 0.0
    
    if provider == "gemini":
        model = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")
        return GeminiChatSession(model, system_instruction, tools, temperature)
    elif provider == "kimi":
        model = os.environ.get("LLM_MODEL", "moonshot-v1-8k")
        api_key = os.environ.get("KIMI_API_KEY")
        if not api_key:
            raise ValueError("KIMI_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.moonshot.cn/v1", api_key)
    elif provider == "deepseek":
        model = os.environ.get("LLM_MODEL", "deepseek-chat")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set.")
        return OpenAIChatSession(model, system_instruction, tools, temperature, "https://api.deepseek.com", api_key)
    else:
        raise ValueError(f"Unknown LLM Provider: {provider}")
