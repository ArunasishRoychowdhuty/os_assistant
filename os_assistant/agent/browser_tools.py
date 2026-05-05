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


class BrowserDOMController(BrowserTools):
    """DOM query/click/type through Chrome DevTools Protocol when available."""

    def query(self, selector: str) -> dict:
        if not selector:
            return {"success": False, "error": "Empty CSS selector"}
        expression = self._query_expression(selector)
        return self._runtime_evaluate(expression)

    def click(self, selector: str) -> dict:
        if not selector:
            return {"success": False, "error": "Empty CSS selector"}
        expression = self._click_expression(selector)
        return self._runtime_evaluate(expression)

    def type_text(self, selector: str, text: str) -> dict:
        if not selector:
            return {"success": False, "error": "Empty CSS selector"}
        expression = self._type_expression(selector, text)
        return self._runtime_evaluate(expression)

    def _runtime_evaluate(self, expression: str) -> dict:
        tab = self._first_page_tab()
        if not tab.get("success"):
            return tab
        websocket_url = tab.get("webSocketDebuggerUrl")
        if not websocket_url:
            return {"success": False, "error": "DevTools tab has no websocket endpoint"}
        try:
            import websocket  # type: ignore
        except Exception:
            return {
                "success": False,
                "error": "Install websocket-client to enable BrowserDOMController actions.",
            }
        try:
            ws = websocket.create_connection(websocket_url, timeout=2)
            payload = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expression,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            }
            ws.send(json.dumps(payload))
            while True:
                message = json.loads(ws.recv())
                if message.get("id") == 1:
                    ws.close()
                    if "error" in message:
                        return {"success": False, "error": message["error"]}
                    value = message.get("result", {}).get("result", {}).get("value")
                    if isinstance(value, dict) and value.get("success") is False:
                        return value
                    return {"success": True, "result": value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _first_page_tab(self) -> dict:
        tabs = self.get_tabs()
        if not tabs.get("success"):
            return tabs
        for tab in tabs.get("tabs", []):
            if tab.get("type") == "page":
                return {"success": True, **tab}
        return {"success": False, "error": "No browser page tab found"}

    @staticmethod
    def _query_expression(selector: str) -> str:
        selector_json = json.dumps(selector)
        return (
            "(() => {"
            f"const el = document.querySelector({selector_json});"
            "if (!el) return {success:false,error:'Element not found'};"
            "const r = el.getBoundingClientRect();"
            "return {success:true, text: el.innerText || el.value || el.getAttribute('aria-label') || '', "
            "tag: el.tagName, rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom}, "
            "visible: !!(r.width || r.height)};"
            "})()"
        )

    @staticmethod
    def _click_expression(selector: str) -> str:
        selector_json = json.dumps(selector)
        return (
            "(() => {"
            f"const el = document.querySelector({selector_json});"
            "if (!el) return {success:false,error:'Element not found'};"
            "el.scrollIntoView({block:'center', inline:'center'});"
            "el.focus(); el.click();"
            "return {success:true, clicked:true, tag:el.tagName};"
            "})()"
        )

    @staticmethod
    def _type_expression(selector: str, text: str) -> str:
        selector_json = json.dumps(selector)
        text_json = json.dumps(text)
        return (
            "(() => {"
            f"const el = document.querySelector({selector_json});"
            "if (!el) return {success:false,error:'Element not found'};"
            "el.scrollIntoView({block:'center', inline:'center'});"
            "el.focus();"
            f"el.value = {text_json};"
            "el.dispatchEvent(new Event('input', {bubbles:true}));"
            "el.dispatchEvent(new Event('change', {bubbles:true}));"
            "return {success:true, typed:true, tag:el.tagName};"
            "})()"
        )
