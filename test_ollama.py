import openai
import json
client = openai.OpenAI(api_key='ollama', base_url='http://localhost:11434/v1')

msgs = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': 'Search for test'},
    {
        'role': 'assistant',
        'content': 'Thought: let me search',
        'tool_calls': [
            {
                'id': 'call_123',
                'type': 'function',
                'function': {
                    'name': 'search_web',
                    'arguments': '{"query":"test"}'
                }
            }
        ]
    },
    {
        'role': 'tool',
        'tool_call_id': 'call_123',
        'name': 'search_web',
        'content': 'Result found: TEST is a success'
    }
]

tools = [{
    'type': 'function',
    'function': {
        'name': 'search_web',
        'description': 'Search the web',
        'parameters': {
            'type': 'object',
            'properties': {'query': {'type': 'string'}}
        }
    }
}]

try:
    res = client.chat.completions.create(model='qwen2.5-coder:14b', messages=msgs, tools=tools)
    print("SUCCESS: ", res.choices[0].message.content)
except Exception as e:
    print("FAILED: ", e)
