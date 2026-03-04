import os
import subprocess
import sys
from google import genai
from google.genai import types
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()

def read_file(filepath: str) -> str:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {filepath}: {e}"

def write_file(filepath: str, content: str) -> str:
    try:
        preview = content[:500] + "..." if len(content) > 500 else content
        console.print(Panel(f"[bold yellow]Agent wants to write to file:[/bold yellow]\n{filepath}\n\n[bold yellow]Content Preview:[/bold yellow]\n{preview}", title="Security Check", border_style="yellow"))
        if not Confirm.ask("[bold red]Allow this file write operation?[/bold red]"):
            return "Operation cancelled by user."
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"File {filepath} written successfully."
    except Exception as e:
        return f"Error writing file {filepath}: {e}"

def execute_command(command: str) -> str:
    try:
        console.print(Panel(f"[bold yellow]Agent wants to execute command:[/bold yellow]\n{command}", title="Security Check", border_style="red"))
        if not Confirm.ask("[bold red]Allow this command to be executed?[/bold red]"):
            return "Operation cancelled by user."
            
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

TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "execute_command": execute_command
}

def main():
    console.print(Panel.fit("[bold cyan]Welcome to clawyu Local AI Agent[/bold cyan]\nType your request below. Type 'exit' to quit.", border_style="cyan"))
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error: GEMINI_API_KEY environment variable not set.[/bold red]")
        console.print("Please set it before running clawyu.")
        sys.exit(1)

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        console.print(f"[bold red]Failed to initialize Gemini Client: {e}[/bold red]")
        sys.exit(1)

    config = types.GenerateContentConfig(
        system_instruction=(
            "You are clawyu, a highly capable local AI agent. You have access to the user's local system "
            "through function calling. You can read files, write files, and execute shell commands. "
            "You run on Windows. When you need to do something on the user's system, USE THE TOOLS. "
            "Don't just give the user instructions to do it themselves unless you cannot do it or the user explicitly asks how to do it. "
            "All write and execute operations will prompt the user for confirmation, so you don't need "
            "to ask for permission first, just call the tool. Be helpful, concise, and proactive. "
            "When executing commands, remember the OS is Windows (Powershell/CMD)."
        ),
        tools=[read_file, write_file, execute_command],
        temperature=0.0, 
    )
    
    try:
        chat = client.chats.create(model="gemini-2.5-flash", config=config)
    except Exception as e:
        console.print(f"[bold red]Error creating chat session: {e}[/bold red]")
        sys.exit(1)

    while True:
        try:
            user_input = console.input("\n[bold green]You:[/bold green] ")
            if not user_input.strip():
                continue
            if user_input.lower() in ['exit', 'quit']:
                console.print("[bold cyan]Goodbye![/bold cyan]")
                break

            console.print("[dim]Thinking...[/dim]")
            
            response = chat.send_message(user_input)

            while response.function_calls:
                tool_results = []
                
                for function_call in response.function_calls:
                    name = function_call.name
                    args = function_call.args
                    
                    if name in TOOL_MAP:
                        console.print(f"[dim]Executing tool: {name}...[/dim]")
                        try:
                            func_args = {k: v for k, v in args.items()}
                            result = TOOL_MAP[name](**func_args)
                        except Exception as e:
                            result = f"Error calling tool {name}: {e}"
                        
                        tool_results.append(types.Part.from_function_response(
                            name=name,
                            response={"result": result}
                        ))
                    else:
                        tool_results.append(types.Part.from_function_response(
                            name=name,
                            response={"error": f"Tool {name} not found"}
                        ))
                
                console.print("[dim]Analyzing results...[/dim]")
                response = chat.send_message(tool_results)

            if response.text:
                console.print("\n[bold blue]clawyu:[/bold blue]")
                console.print(Markdown(response.text))

        except KeyboardInterrupt:
            console.print("\n[bold cyan]Goodbye![/bold cyan]")
            break
        except Exception as e:
            console.print(f"\n[bold red]An error occurred: {e}[/bold red]")

if __name__ == "__main__":
    main()
