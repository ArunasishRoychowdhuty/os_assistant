import os
import sys
import importlib
import traceback
import logging
import ast
import types

logger = logging.getLogger(__name__)

class SelfEvolutionEngine:
    """
    Dynamic Plugin Architecture & Hot-Reloading System.
    Allows the AI to write, compile, and execute its own Python tools (Skills) live without restarting.
    """
    def __init__(self, memory):
        self.memory = memory
        # Create a dedicated 'skills' folder inside the agent directory
        self.skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        os.makedirs(self.skills_dir, exist_ok=True)
        
        # Add the folder to sys.path so importlib can find the modules
        if self.skills_dir not in sys.path:
            sys.path.insert(0, self.skills_dir)
            
    def propose_skill(self, skill_name: str, python_code: str) -> dict:
        """Syntax-checks and sandbox-tests a new Python skill, but requires registry activation."""
        skill_name = skill_name.replace(" ", "_").replace("-", "_").lower()
        if not skill_name.isidentifier():
            return {"success": False, "error": f"Invalid skill name '{skill_name}'. Must be a valid Python identifier."}
            
        file_path = os.path.join(self.skills_dir, f"{skill_name}.py")

        policy = self._validate_skill_policy(python_code)
        if not policy.get("success"):
            return policy

        try:
            compile(python_code, file_path, 'exec')
        except SyntaxError as e:
            error_msg = f"SyntaxError in generated code at line {e.lineno}: {e.msg}"
            self.memory.log_error({"action": "propose_skill", "name": skill_name}, error_msg, "Compile Phase")
            return {"success": False, "error": error_msg}

        test = self._sandbox_test_skill(skill_name, python_code)
        if not test.get("success"):
            self.memory.log_error({"action": "propose_skill", "name": skill_name}, test["error"], "Sandbox Test")
            return test

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(python_code)
        except Exception as e:
            return {"success": False, "error": f"Failed to save skill proposal file: {e}"}

        return {
            "success": True, 
            "message": f"Skill '{skill_name}' successfully proposed and validated in simulation! Action required: You must use 'activate_skill' to enable it."
        }

    def create_and_load_skill(self, skill_name: str, python_code: str) -> dict:
        """Compatibility path: validate, save, and activate a skill in one call."""
        proposed = self.propose_skill(skill_name, python_code)
        if not proposed.get("success"):
            return proposed

        normalized_name = skill_name.replace(" ", "_").replace("-", "_").lower()
        activated = self.activate_skill(normalized_name)
        if not activated.get("success"):
            return activated

        return {
            "success": True,
            "message": f"Skill '{normalized_name}' successfully created and loaded.",
        }
        
    def activate_skill(self, skill_name: str) -> dict:
        """Activates a proposed skill by injecting it into the live running app."""
        file_path = os.path.join(self.skills_dir, f"{skill_name}.py")
        if not os.path.exists(file_path):
            return {"success": False, "error": f"Proposed skill '{skill_name}' not found."}
            
        if self.skills_dir not in sys.path:
            sys.path.insert(0, self.skills_dir)
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                python_code = f.read()
                
            module = types.ModuleType(skill_name)
            module.__file__ = file_path
            module.__source__ = python_code
            exec(compile(python_code, file_path, "exec"), module.__dict__)
            sys.modules[skill_name] = module
                
            if not hasattr(module, 'run'):
                os.remove(file_path)
                if skill_name in sys.modules:
                    del sys.modules[skill_name]
                return {"success": False, "error": "Skill module must define a 'def run(**kwargs):' function."}
                
            success_msg = f"I have successfully activated a new skill. I can now '{skill_name}'."
            self.memory.learn_user_preference(success_msg)
            
            return {
                "success": True, 
                "message": f"Skill '{skill_name}' successfully activated and hot-reloaded! You can now use execute_skill."
            }
            
        except Exception as e:
            # Revert on failure
            if os.path.exists(file_path):
                os.remove(file_path)
            if skill_name in sys.modules:
                del sys.modules[skill_name]
            error_msg = f"Failed to activate/reload skill: {str(e)}\n{traceback.format_exc()}"
            self.memory.log_error({"action": "activate_skill", "name": skill_name}, error_msg, "Import Phase")
            return {"success": False, "error": error_msg}

    @staticmethod
    def _validate_skill_policy(python_code: str) -> dict:
        blocked_imports = {"os", "subprocess", "socket", "ctypes", "shutil", "winreg"}
        blocked_calls = {"open", "eval", "exec", "compile", "__import__"}
        try:
            tree = ast.parse(python_code)
        except SyntaxError as e:
            return {"success": False, "error": f"SyntaxError at line {e.lineno}: {e.msg}"}
        has_run = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run":
                has_run = True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in blocked_imports:
                        return {"success": False, "error": f"Blocked skill import: {alias.name}"}
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in blocked_imports:
                return {"success": False, "error": f"Blocked skill import: {node.module}"}
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in blocked_calls:
                return {"success": False, "error": f"Blocked skill call: {node.func.id}"}
        if not has_run:
            return {"success": False, "error": "Skill module must define a 'def run(**kwargs):' function."}
        return {"success": True}

    @staticmethod
    def _sandbox_test_skill(skill_name: str, python_code: str) -> dict:
        module = types.ModuleType(skill_name)
        safe_builtins = {
            "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
            "enumerate": enumerate, "float": float, "int": int, "len": len,
            "list": list, "max": max, "min": min, "range": range, "round": round,
            "str": str, "sum": sum, "tuple": tuple,
        }
        try:
            env = {"__builtins__": safe_builtins}
            exec(compile(python_code, f"<skill:{skill_name}>", "exec"), env)
            result = env["run"]()
            return {"success": True, "test_result": str(result)[:200]}
        except TypeError:
            return {"success": True, "warning": "run() requires params; syntax and policy passed"}
        except Exception as e:
            return {"success": False, "error": f"Skill sandbox test failed: {e}"}
            
    def execute_skill(self, skill_name: str, params: dict = None) -> dict:
        """Executes a previously learned skill."""
        if params is None:
            params = {}
            
        try:
            if skill_name not in sys.modules:
                file_path = os.path.join(self.skills_dir, f"{skill_name}.py")
                if not os.path.exists(file_path):
                    return {"success": False, "error": f"Skill '{skill_name}' not found"}
                with open(file_path, "r", encoding="utf-8") as f:
                    python_code = f.read()
                policy = self._validate_skill_policy(python_code)
                if not policy.get("success"):
                    return policy
                module = types.ModuleType(skill_name)
                module.__file__ = file_path
                module.__source__ = python_code
                exec(compile(python_code, file_path, "exec"), module.__dict__)
                sys.modules[skill_name] = module
            else:
                module = sys.modules[skill_name]
                source = getattr(module, "__source__", "")
                if source:
                    policy = self._validate_skill_policy(source)
                    if not policy.get("success"):
                        return policy
                
            # Execute the skill
            result = module.run(**params)
            return {"success": True, "result": str(result)}
            
        except Exception as e:
            error_msg = f"Skill execution failed: {str(e)}\n{traceback.format_exc()}"
            self.memory.log_error({"action": "execute_skill", "name": skill_name}, error_msg, "Run Phase")
            return {"success": False, "error": error_msg}
