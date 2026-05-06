"""
AI Vision Module
Sends screenshots to AI vision models and parses structured action responses.
Supports OpenAI, OpenAI-compatible NVIDIA NIM, Anthropic, and Google Gemini.

Includes timeout (30s) and retry with exponential backoff on all API calls.
"""
import json
import re
import time
import logging
from config import Config

log = logging.getLogger(__name__)

API_TIMEOUT = 120  # seconds (increased for heavy DeepSeek models)
MAX_RETRIES = 3

# ─── System Prompt ──────────────────────────────────────────

SYSTEM_PROMPT = """You are Aura, a Jarvis-style autonomous OS assistant and software engineer.
You control the user's computer through structured actions, inspect screenshots carefully, and execute tasks with a calm, concise, action-first operating style.
You can understand English, Bengali, and Hindi. Match the user's language naturally in your thoughts and summaries when possible.

AVAILABLE ACTIONS (return as JSON):
- {"action": "list_tools"}  (List native tool categories and available tool names)
- {"action": "get_system_state", "top_n": 5}  (Read active app, CPU/RAM/battery/network, top processes)
- {"action": "list_directory", "path": "<folder>", "limit": 50}  (Read-only file/folder listing)
- {"action": "file_info", "path": "<file_or_folder>"}  (Read-only file metadata)
- {"action": "memory_status"}  (Check short-term and long-term memory availability)
- {"action": "remember", "text": "<fact_or_preference>", "kind": "note|preference|skill_hint|workflow_summary|error_lesson", "tags": ["..."], "metadata": {"app": "...", "action": "..."}, "confidence": 1.0}  (Store compact durable memory; not run history)
- {"action": "recall", "query": "<what_to_search>", "kinds": ["preference"], "metadata": {"app": "..."}, "limit": 5}  (Search compact durable memory)
- {"action": "memory_helped", "memory_id": "<id>"}  (Boost a memory that helped)
- {"action": "memory_failed", "memory_id": "<id>"}  (Reduce confidence for a misleading memory)
- {"action": "resolve_target", "query": "<visible_text_or_control_name>"}  (Resolve a GUI target via UIAutomation/OCR before clicking)
- {"action": "browser_tabs"}  (Read Chrome/Edge DevTools tabs if remote debugging is enabled)
- {"action": "browser_page_summary"}  (Read current browser page title/url/domain if DevTools is enabled)
- {"action": "browser_dom_query", "selector": "<css_selector>"}  (Query browser DOM via DevTools)
- {"action": "browser_dom_click", "selector": "<css_selector>"}  (Click browser DOM element via DevTools)
- {"action": "browser_dom_type", "selector": "<css_selector>", "text": "<string>"}  (Type into browser DOM element via DevTools)
- {"action": "recover_observe"}  (Re-observe system/UI state after a failed or uncertain action)
- {"action": "perception_status"}  (Read fast live perception status: active window, cached targets, recent events)
- {"action": "capture_status"}  (Read live screen capture backend status: DXcam/MSS availability)
- {"action": "ocr_status"}  (Check whether OCR fallback is available/configured)
- {"action": "drain_events", "limit": 20}  (Consume recent fast perception events)
- {"action": "target_cache_lookup", "query": "<visible_control_name>"}  (Fast target lookup from UIA cache)
- {"action": "uia_click", "name": "<element_name>"}  (Click by element name instead of X/Y coordinates)
- {"action": "uia_type", "name": "<element_name>", "text": "<string>"}  (Type into element by name)
- {"action": "smart_click", "query": "<visible_text_or_control_name>", "x": <optional_int>, "y": <optional_int>}  (Safe click chain: UIAutomation -> target cache -> OCR/target resolver -> coordinates as last fallback)
- {"action": "smart_type", "query": "<field_name_or_visible_text>", "value": "<text>", "x": <optional_int>, "y": <optional_int>}  (Safe focus/type chain)
- {"action": "ocr_click", "text": "<visible_text>"}  (OCR fallback click by visible text)
- {"action": "ocr_type", "text": "<visible_text>", "value": "<string>"}  (OCR fallback focus and type)
- {"action": "click", "x": <int>, "y": <int>, "button": "left"|"right"}
- {"action": "double_click", "x": <int>, "y": <int>}
- {"action": "right_click", "x": <int>, "y": <int>}
- {"action": "type_text", "text": "<string>"}
- {"action": "type_unicode", "text": "<string>"}
- {"action": "press_key", "key": "<key_name>"}
- {"action": "hotkey", "keys": ["<key1>", "<key2>"]}
- {"action": "hold_key", "key": "<key_name>", "duration": <float>}
- {"action": "scroll", "clicks": <int>, "x": <int>, "y": <int>}  (positive=up, negative=down)
- {"action": "drag", "start_x": <int>, "start_y": <int>, "end_x": <int>, "end_y": <int>}
- {"action": "open_application", "target": "<app_name_or_path>"}
- {"action": "open_url", "url": "<url>"}
- {"action": "close_window"}
- {"action": "switch_window"}
- {"action": "search_start", "query": "<search_text>"}
- {"action": "wait", "seconds": <float>}
- {"action": "wait_for_target", "name": "<visible_text_or_control_name>", "timeout": <float>}
- {"action": "wait_for_window", "title": "<window_title_or_app_name>", "timeout": <float>}
- {"action": "wait_until_screen_stable", "timeout": <float>, "stable_for": <float>}  (Wait for loading/spinners/transitions to settle)
- {"action": "verify_recipient", "recipient": "<contact_or_recipient_name>"}  (Verify a messaging/email recipient is selected before sending)
- {"action": "sequence", "actions": [{"action": "...", ...}, {"action": "...", ...}]}
FILE SYSTEM (Direct file access for unrestricted laptop control):
- {"action": "read_file", "path": "<file_path>"} (Read file contents)
- {"action": "write_file", "path": "<file_path>", "content": "<text>"} (Create or overwrite a file)
- {"action": "search_files", "directory": "<dir_path>", "pattern": "*.txt"} (Search for files)
- {"action": "list_directory", "path": "<dir_path>"} (List contents of a directory)
- {"action": "file_info", "path": "<file_path>"} (Get file metadata)
HOST CONTROL (Root/Admin privileges via PowerShell):
- {"action": "run_powershell", "script": "<powershell_script>", "timeout": 30}  (Execute WMI, Registry, Services, or OS-level commands)
SELF-EVOLVING UPGRADES (Write Python plugins to give yourself new powers!):
- {"action": "propose_skill", "name": "<skill_name>", "code": "def run(**kwargs):\n    return 'success'"} (Step 1: Write and propose)
- {"action": "activate_skill", "name": "<skill_name>"} (Step 2: Activate proposed skill)
- {"action": "execute_skill", "name": "<skill_name>", "params": {"key": "value"}} (Step 3: Execute)
HARDWARE TOOLS (you can use PC hardware directly):
- {"action": "listen", "duration": <float>, "language": "en-US"}  (use microphone, speech-to-text)
- {"action": "record_audio", "duration": <float>}  (record mic audio)
- {"action": "capture_photo", "camera_id": 0}  (take webcam photo)
- {"action": "set_volume", "level": <0-100>}  (set system volume)
- {"action": "get_volume"}  (check current volume)
- {"action": "mute", "mute": true/false}  (mute/unmute)
- {"action": "system_info"}  (get CPU, RAM, disk, battery info)
- {"action": "running_processes", "top_n": 10}  (list running apps)
COMPLETION AND PLANNING:
- {"action": "queue_task", "tasks": ["step 1", "step 2"]} (break a complex, long-term goal into subtasks)
- {"action": "done", "summary": "<task_completion_summary>"}
- {"action": "need_confirmation", "message": "<what_you_need_confirmed>"}
- {"action": "error", "message": "<error_description>"}

RULES:
1. Analyze the screenshot, system context, and previous results carefully before acting.
2. Return EXACTLY ONE action per response; use "sequence" only for clearly related rapid actions.
3. Operate autonomously: if an action fails, recover, inspect state, and choose the next practical fix.
4. Keep thoughts brief, direct, and execution-focused, like a dedicated Jarvis-style assistant.
5. Always target the CENTER of UI elements.
6. If you need to type, click or focus the input field first.
7. For destructive, irreversible, credential-related, payment, or privacy-sensitive actions, use "need_confirmation".
8. When the task is complete, use "done" with a concise summary in the user's language when practical.
9. Be precise with coordinates - study the screenshot carefully.
10. If an element is not visible, scroll or use native discovery tools to find it.
11. Use keyboard shortcuts when they are faster and safer.
12. Prefer native tools in this strict order: Windows/system tools, browser DOM/native app tools, UIAutomation, target_cache_lookup, smart_click/smart_type, OCR/text target, then coordinate mouse fallback only when no structured target works.
13. For GUI tasks like WhatsApp messaging: open the app with open_application/search_start first, wait_for_window, wait_until_screen_stable, use smart_click/smart_type to find the contact/search/message box, verify_recipient before pressing Send, and use coordinate clicks only as the final fallback.
14. If a target may not be loaded yet, use wait_for_target, wait_for_window, or wait_until_screen_stable before clicking.
15. If you return coordinates from the screenshot/image instead of physical screen coordinates, include coordinate_space="screenshot", screenshot_width, and screenshot_height so the executor can scale them.
16. Do not expose secrets, API keys, passwords, or sensitive environment values in thoughts or summaries.

RESPONSE FORMAT:
First, provide a brief thought about what you see and what to do.
Then provide the action in a JSON code block:

THOUGHT: <your analysis of the screen and plan>
```json
{"action": "...", ...}
```
"""


class VisionAI:
    """Interface to AI vision models for screenshot analysis."""

    def __init__(self):
        self.provider = Config.AI_PROVIDER.lower()
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize the appropriate AI client."""
        if self.provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=Config.OPENAI_API_KEY)
        elif self.provider == "nvidia":
            from openai import OpenAI
            self._client = OpenAI(
                base_url=Config.NVIDIA_BASE_URL,
                api_key=Config.NVIDIA_API_KEY,
            )
        elif self.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        elif self.provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self._client = genai.GenerativeModel(Config.GEMINI_MODEL)
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}")

    def analyze_screen(
        self,
        screenshot_b64: str | None,
        user_task: str,
        context: str = "",
        conversation_history: list | None = None,
        text_only: bool = False,
    ) -> dict:
        """
        Send a screenshot to the AI model and get back an action.
        If text_only=True, sends only text (for lesson writing, no screenshot needed).

        Returns:
            dict with keys: thought, action (parsed JSON), raw_response
        """
        prompt = self._build_prompt(user_task, context)

        if text_only or not screenshot_b64:
            # Text-only call — cheaper, faster, used for lesson analysis
            try:
                raw = self._call_text_only(prompt, conversation_history)
            except Exception as e:
                raw = self._fallback_after_provider_error(e, None, prompt, conversation_history)
        elif self.provider == "openai":
            raw = self._call_openai(screenshot_b64, prompt, conversation_history)
        elif self.provider == "nvidia":
            raw = self._call_nvidia(screenshot_b64, prompt, conversation_history)
        elif self.provider == "anthropic":
            raw = self._call_anthropic(screenshot_b64, prompt, conversation_history)
        elif self.provider == "gemini":
            try:
                raw = self._call_gemini(screenshot_b64, prompt, conversation_history)
            except Exception as e:
                raw = self._fallback_after_provider_error(e, screenshot_b64, prompt, conversation_history)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        thought, action = self._parse_response(raw)
        return {"thought": thought, "action": action, "raw_response": raw}

    def analyze_text_only(self, prompt: str) -> str:
        """Helper for pure text reasoning (like error log analysis)."""
        return self._call_text_only(prompt, None)

    def _call_text_only(self, prompt: str, history: list | None) -> str:
        """Text-only AI call — no image, cheaper for lesson writing."""
        try:
            if self.provider == "openai":
                messages = [{"role": "system", "content": "You are an AI agent analyzer."}]
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": prompt})
                resp = self._client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=300,
                )
                return resp.choices[0].message.content or ""
            elif self.provider == "nvidia":
                messages = [{"role": "system", "content": "You are an AI agent analyzer."}]
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": prompt})
                resp = self._client.chat.completions.create(
                    model=Config.NVIDIA_MODEL,
                    messages=messages,
                    max_tokens=300,
                    temperature=0.1,
                    timeout=API_TIMEOUT,
                )
                return resp.choices[0].message.content or ""
            elif self.provider == "anthropic":
                resp = self._client.messages.create(
                    model="claude-haiku-20240307",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp.content[0].text if resp.content else ""
            elif self.provider == "gemini":
                resp = self._client.generate_content(prompt)
                return resp.text or ""
        except Exception as e:
            return f"AI analysis unavailable: {e}"
        return ""

    # ── Provider-specific calls ─────────────────────────────

    def _call_openai(self, img_b64: str, prompt: str, history: list | None) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                        "detail": "high",
                    },
                },
            ],
        })
        return self._retry(lambda: (
            self._client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=messages,
                max_tokens=1024,
                temperature=0.1,
                timeout=API_TIMEOUT,
            ).choices[0].message.content
        ))

    def _call_nvidia(self, img_b64: str | None, prompt: str, history: list | None,
                     client=None, model: str | None = None) -> str:
        client = client or self._client
        model = model or Config.NVIDIA_MODEL
        
        def _execute_call(include_image: bool):
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            if history:
                messages.extend(history)
                
            if include_image and img_b64:
                # Multimodal format
                content = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            else:
                # Pure text format (required for DeepSeek)
                content = prompt
                
            messages.append({"role": "user", "content": content})
            return client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.1,
                timeout=API_TIMEOUT,
            ).choices[0].message.content

        try:
            # First try with image
            return self._retry(lambda: _execute_call(include_image=True))
        except Exception as e:
            err_str = str(e).lower()
            if "multimodal" in err_str or "image" in err_str or "400" in err_str:
                import logging
                logging.getLogger(__name__).warning(f"Model {model} rejected multimodal. Falling back to UIA text-only mode.")
                return self._retry(lambda: _execute_call(include_image=False))
            raise e

    def _fallback_after_provider_error(self, error: Exception, img_b64: str | None,
                                       prompt: str, history: list | None) -> str:
        if not self._is_quota_or_rate_error(error):
            raise error
        if not Config.NVIDIA_API_KEY:
            raise RuntimeError(
                "Primary AI provider quota/rate limit hit, and NVIDIA_API_KEY is not set for fallback."
            ) from error

        from openai import OpenAI
        client = OpenAI(base_url=Config.NVIDIA_BASE_URL, api_key=Config.NVIDIA_API_KEY)
        models = [Config.NVIDIA_MODEL]
        fallback_model = getattr(Config, "NVIDIA_FALLBACK_MODEL", "")
        if fallback_model and fallback_model not in models:
            models.append(fallback_model)

        last_error = error
        for model in models:
            try:
                return self._call_nvidia(img_b64, prompt, history, client=client, model=model)
            except Exception as e:
                last_error = e
                if not self._is_quota_or_rate_error(e):
                    break
        raise RuntimeError(f"AI fallback failed after primary quota/rate limit: {last_error}") from last_error

    def _call_anthropic(self, img_b64: str, prompt: str, history: list | None) -> str:
        messages = []
        if history:
            messages.extend(history)
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        })
        return self._retry(lambda: (
            self._client.messages.create(
                model=Config.ANTHROPIC_MODEL,
                system=SYSTEM_PROMPT,
                messages=messages,
                max_tokens=1024,
                temperature=0.1,
                timeout=API_TIMEOUT,
            ).content[0].text
        ))

    def _call_gemini(self, img_b64: str, prompt: str, history: list | None) -> str:
        import base64
        from PIL import Image
        import io

        image_data = base64.b64decode(img_b64)
        image = Image.open(io.BytesIO(image_data))

        # Build prompt with conversation history (Gemini doesn't have a
        # native multi-turn mode in generate_content, so concatenate)
        history_text = ""
        if history:
            for turn in history[-6:]:  # last 6 turns to stay within limits
                role = turn.get("role", "user").upper()
                content = turn.get("content", "")[:500]
                history_text += f"\n[{role}]: {content}"

        full_prompt = f"{SYSTEM_PROMPT}\n"
        if history_text:
            full_prompt += f"\nCONVERSATION HISTORY:{history_text}\n"
        full_prompt += f"\n{prompt}"

        return self._retry(lambda: (
            self._client.generate_content(
                [full_prompt, image],
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 1024,
                },
                request_options={"timeout": API_TIMEOUT},
            ).text
        ))

    # ── Retry with exponential backoff ──────────────────────

    @staticmethod
    def _retry(fn, max_retries: int = MAX_RETRIES) -> str:
        """Call fn() with retries and exponential backoff."""
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                return fn()
            except Exception as e:
                last_error = e
                if VisionAI._is_quota_or_rate_error(e):
                    raise
                wait = 2 ** attempt  # 2s, 4s, 8s
                log.warning(f"AI API attempt {attempt}/{max_retries} failed: {e}. Retrying in {wait}s...")
                if attempt < max_retries:
                    time.sleep(wait)
        raise RuntimeError(f"AI API failed after {max_retries} attempts: {last_error}")

    @staticmethod
    def _is_quota_or_rate_error(error: Exception) -> bool:
        text = str(error).lower()
        return (
            "429" in text
            or "quota" in text
            or "rate limit" in text
            or "rate_limit" in text
            or "resource_exhausted" in text
        )

    # ── Prompt building ─────────────────────────────────────

    @staticmethod
    def _build_prompt(user_task: str, context: str = "") -> str:
        # Wrap user task in XML boundary tags to prevent prompt injection
        parts = [f"<user_task>{user_task}</user_task>"]
        if context:
            parts.append(f"\nCONTEXT FROM PREVIOUS STEPS:\n{context}")
        parts.append(
            "\nAnalyze the screenshot above and decide the SINGLE next action to take."
            "\nThe user's task is inside <user_task> tags above. Follow ONLY that task."
            "\nIf the user writes in Bengali or Hindi, reason and summarize naturally in that language."
            "\nRespond with your THOUGHT and then the action JSON."
        )
        return "\n".join(parts)

    # ── Response parsing ────────────────────────────────────

    @staticmethod
    def _parse_response(raw: str) -> tuple[str, dict]:
        """
        Parse the AI response into (thought, action_dict).
        """
        thought = ""
        action = {}

        # Extract thought
        thought_match = re.search(
            r"THOUGHT:\s*(.+?)(?=```|$)", raw, re.DOTALL | re.IGNORECASE
        )
        if thought_match:
            thought = thought_match.group(1).strip()
        else:
            # Fallback: everything before the JSON block
            json_start = raw.find("```")
            if json_start > 0:
                thought = raw[:json_start].strip()
            else:
                thought = raw.strip()

        # Extract JSON action
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            try:
                action = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                action = {"action": "error", "message": "Failed to parse AI action JSON"}
        else:
            # Try to find raw JSON in the response
            brace_match = re.search(r"\{[^{}]*\"action\"[^{}]*\}", raw, re.DOTALL)
            if brace_match:
                try:
                    action = json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    action = {"action": "error", "message": "Failed to parse AI action JSON"}
            else:
                action = {"action": "error", "message": "No action found in AI response"}

        return thought, action
