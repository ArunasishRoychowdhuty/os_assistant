import subprocess
import logging

logger = logging.getLogger(__name__)

class HostController:
    """Native OS control via PowerShell (Sub-Agent for Root/Admin tasks)."""
    
    @staticmethod
    def run_powershell(script: str, timeout: int = 30) -> dict:
        """Execute a PowerShell script and return the result."""
        try:
            logger.info(f"Executing PowerShell: {script[:100]}...")
            
            # Ensure execution policy bypass for current process, no profile loading for speed
            cmd = [
                "powershell", 
                "-NoProfile", 
                "-NonInteractive", 
                "-ExecutionPolicy", "Bypass",
                "-Command", 
                script
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False, 
                "error": f"Execution timed out after {timeout} seconds. Script might be stuck or waiting for input.",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "success": False, 
                "error": f"Failed to execute PowerShell: {str(e)}",
                "exit_code": -1
            }
