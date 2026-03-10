import os
import sys
import importlib
import inspect
from typing import List, Callable

class PluginManager:
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = plugins_dir
        self.tools: List[Callable] = []
        
    def load_plugins(self) -> List[Callable]:
        """Scans the plugins directory and loads all callable tools."""
        self.tools = []
        
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
            return self.tools
            
        # Ensure plugins directory is in the Python path
        if self.plugins_dir not in sys.path:
            sys.path.append(os.path.abspath('.'))
            
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = f"{self.plugins_dir}.{filename[:-3]}"
                try:
                    # Dynamically import the module
                    module = importlib.import_module(module_name)
                    
                    # Reload to ensure we get fresh code if modified
                    importlib.reload(module)
                    
                    # Find all functions in the module that are defined in it (not imported)
                    # and have a docstring (assuming docstrings mean they are intended as tools)
                    for name, obj in inspect.getmembers(module):
                        if inspect.isfunction(obj) and obj.__module__ == module.__name__:
                            if obj.__doc__: # Only add functions with docstrings
                                self.tools.append(obj)
                                print(f"Loaded plugin tool: {name} from {filename}")
                except Exception as e:
                    print(f"Error loading plugin {filename}: {e}")
                    
        return self.tools

    def get_tools(self) -> List[Callable]:
        """Returns the currently loaded tools."""
        return self.tools

# Singleton instance
plugin_manager = PluginManager()
