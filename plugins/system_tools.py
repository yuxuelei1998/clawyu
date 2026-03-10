import os
import subprocess
from datetime import datetime

def list_directory(dir_path: str) -> str:
    """Lists the contents of a directory using its absolute path."""
    try:
        files = os.listdir(dir_path)
        return f"Contents of {dir_path}:\n" + "\n".join(files)
    except Exception as e:
        return f"Error listing directory {dir_path}: {e}"

def get_current_time() -> str:
    """Gets the current local date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def read_file(filepath: str) -> str:
    """Reads the contents of a local file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {filepath}: {e}"

def write_file_sync(filepath: str, content: str) -> str:
    """Writes content to a local file. IMPORTANT: Will prompt user for authorization."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"File {filepath} written successfully."
    except Exception as e:
        return f"Error writing file {filepath}: {e}"

def execute_command_sync(command: str) -> str:
    """Executes a shell command. IMPORTANT: Will prompt user for authorization."""
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
