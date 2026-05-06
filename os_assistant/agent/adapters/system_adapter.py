"""
System Adapter
Handles OS-level processes, application launching, and terminal execution.
Replaces the application/URL functions from the legacy actions.py.
"""
import time
import subprocess
import shlex

class SystemAdapter:
    SHELL_INJECTION_CHARS = ['|', '&', ';', '`', '$', '>', '<', '(', ')', '{', '}', '^']
    SHELL_INJECTION_PATTERNS = [
        'cmd /c', 'cmd.exe /c', 'cmd /k',
        'powershell -c', 'powershell.exe -c',
        'powershell -enc', 'powershell -e ',
        'invoke-expression', 'iex ', 'iex(',
        'start-process',
        '/c ', '/k ',
    ]

    @staticmethod
    def open_application(name_or_path: str) -> dict:
        """
        Open an application. Optimized for fast terminal launch to skip GUI menus.
        """
        target = name_or_path.strip()

        if not target:
            return {"action": "open_app", "target": target, "success": False, "error": "Empty target"}

        target_lower = target.lower()
        for char in SystemAdapter.SHELL_INJECTION_CHARS:
            if char in target:
                return {"action": "open_app", "success": False, "error": f"Blocked: character '{char}'"}

        for pattern in SystemAdapter.SHELL_INJECTION_PATTERNS:
            if pattern in target_lower:
                return {"action": "open_app", "success": False, "error": f"Blocked: pattern '{pattern}'"}

        try:
            # Try running as a process first
            try:
                args = shlex.split(target)
            except ValueError:
                args = [target]
            subprocess.Popen(args, shell=False)
            time.sleep(1.0) # Reduced from 1.5s for faster hybrid speed
            return {"action": "open_app", "target": target, "success": True, "method": "direct"}
        except FileNotFoundError:
            try:
                # Optimized Start-Process shell execution for generic App names (e.g., 'whatsapp')
                subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", f"Start-Process shell:AppsFolder\\{target}"], shell=False)
                time.sleep(1.5)
                return {"action": "open_app", "target": target, "success": True, "method": "powershell_appsfolder"}
            except Exception as e2:
                try:
                    # Final fallback to explorer
                    subprocess.Popen(["explorer.exe", target], shell=False)
                    time.sleep(2.0)
                    return {"action": "open_app", "target": target, "success": True, "method": "explorer"}
                except Exception as e3:
                    return {"action": "open_app", "target": target, "success": False, "error": f"Failed all methods: {str(e3)}"}
        except Exception as e:
            return {"action": "open_app", "target": target, "success": False, "error": str(e)}

    @staticmethod
    def open_url(url: str) -> dict:
        """Open a URL in the default browser."""
        import webbrowser
        if not url.startswith(('http://', 'https://', 'file://')):
            url = 'https://' + url
        webbrowser.open(url)
        return {"action": "open_url", "url": url, "success": True}

    @staticmethod
    def wait(seconds: float) -> dict:
        """Pause execution."""
        time.sleep(max(0.1, seconds))
        return {"action": "wait", "seconds": seconds, "success": True}
