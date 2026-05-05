"""
Browser helper tools.

These are intentionally optional and read-mostly. They improve browser tasks
without requiring direct DOM control unless Chrome/Edge remote debugging is
already enabled by the user.
"""
from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlparse


class BrowserTools:
    def __init__(self, devtools_url: str = "http://127.0.0.1:9222"):
        self.devtools_url = devtools_url.rstrip("/")

    def get_tabs(self) -> dict:
        try:
            with urllib.request.urlopen(f"{self.devtools_url}/json", timeout=1.0) as resp:
                tabs = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "tabs": tabs}
        except Exception as e:
            return {
                "success": False,
                "error": (
                    "Browser DevTools unavailable. Start Chrome/Edge with "
                    "--remote-debugging-port=9222 for DOM-aware browser context."
                ),
                "detail": str(e),
            }

    def active_page_summary(self) -> dict:
        tabs = self.get_tabs()
        if not tabs.get("success"):
            return tabs
        pages = [t for t in tabs.get("tabs", []) if t.get("type") == "page"]
        if not pages:
            return {"success": False, "error": "No browser page tabs found"}
        page = pages[0]
        parsed = urlparse(page.get("url", ""))
        return {
            "success": True,
            "title": page.get("title", ""),
            "url": page.get("url", ""),
            "domain": parsed.netloc,
        }
