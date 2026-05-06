"""
Execution Adapters
Splits the monolithic ComputerActions into specialized execution handlers.
"""
from agent.adapters.input_adapter import InputAdapter
from agent.adapters.system_adapter import SystemAdapter
from agent.adapters.window_adapter import WindowAdapter

__all__ = ["InputAdapter", "SystemAdapter", "WindowAdapter"]
