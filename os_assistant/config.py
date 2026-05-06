"""
OS Assistant Configuration
Supports OpenAI, Anthropic, Google Gemini, and NVIDIA-compatible providers.
"""
import os
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()


class Config:
    # ─── AI Provider Settings ───────────────────────────────────────
    # Supported: "openai", "anthropic", "gemini", "nvidia"
    AI_PROVIDER = os.getenv("AI_PROVIDER", "nvidia")

    # API Keys (set via .env file or environment variables)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "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")
    NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

    # Model names per provider
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
    NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-pro")
    NVIDIA_FALLBACK_MODEL = os.getenv("NVIDIA_FALLBACK_MODEL", "meta/llama-3.1-405b-instruct")

    # ─── Data Directory Settings ────────────────────────────────────
    BASE_DATA_DIR = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), ".os_assistant")

    # ─── Screenshot Settings ────────────────────────────────────────
    SCREENSHOT_DIR = os.path.join(BASE_DATA_DIR, "screenshots")
    SCREENSHOT_QUALITY = 85  # JPEG quality (1-100)
    MAX_SCREENSHOTS = 50  # Max stored screenshots before cleanup
    ENABLE_DXCAM = os.getenv("ENABLE_DXCAM", "true").lower() in ("1", "true", "yes", "on")

    # ─── Memory Settings ────────────────────────────────────────────
    MEMORY_DIR = os.path.join(BASE_DATA_DIR, "memory")
    ENABLE_MEM0 = os.getenv("ENABLE_MEM0", "false").lower() in ("1", "true", "yes", "on")
    MAX_SHORT_TERM_ITEMS = 20
    MAX_LONG_TERM_ITEMS = 100
    MAX_ERROR_MEMORY_ITEMS = 50

    # ─── Safety Settings ────────────────────────────────────────────
    CONFIRM_DESTRUCTIVE = True  # Ask before delete/format operations
    BLOCKED_COMMANDS = [
        "format", "del /s", "rd /s", "rm -rf",
        "shutdown", "restart", "diskpart",
    ]

    # ─── Agent Settings ─────────────────────────────────────────────
    MAX_RETRIES = 3
    ACTION_DELAY = 0.5  # Seconds between actions
    SCREENSHOT_DELAY = 1.0  # Wait after action before screenshot
    SCREEN_SCAN_INTERVAL = float(os.getenv("SCREEN_SCAN_INTERVAL", "0.5"))
    ENABLE_WEBSOCKET_BRIDGE = os.getenv("ENABLE_WEBSOCKET_BRIDGE", "false").lower() in ("1", "true", "yes", "on")

    @classmethod
    def ensure_dirs(cls):
        """Create required directories."""
        os.makedirs(cls.SCREENSHOT_DIR, exist_ok=True)
        os.makedirs(cls.MEMORY_DIR, exist_ok=True)
