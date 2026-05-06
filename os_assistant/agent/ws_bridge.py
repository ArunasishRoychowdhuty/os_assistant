"""
WebSocket Bridge: connects the Electron GUI to the Python Agent backend.
Runs a ws:// server on port 8765 that the Electron main process connects to.
"""
import asyncio
import json
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import websockets
    import websockets.asyncio.server
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class WebSocketBridge:
    """Bridges Electron (Node.js) ↔ Python Agent via WebSocket."""

    def __init__(self, orchestrator, host: str = "127.0.0.1", port: int = 8765):
        self.orchestrator = orchestrator
        self.host = host
        self.port = port
        self._clients: set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        # Register as the orchestrator's event callback
        self.orchestrator._event_callback = self._on_agent_event

    def start(self):
        """Start the WebSocket server in a background thread."""
        if not HAS_WEBSOCKETS:
            logger.error("websockets package not installed. Run: pip install websockets")
            return

        self._thread = threading.Thread(target=self._run_server, daemon=True, name="WS-Bridge")
        self._thread.start()
        logger.info(f"WebSocket bridge started on ws://{self.host}:{self.port}")

    def _run_server(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        async with websockets.asyncio.server.serve(
            self._handler, self.host, self.port
        ):
            await asyncio.Future()  # Run forever

    async def _handler(self, websocket):
        self._clients.add(websocket)
        logger.info(f"Electron client connected ({len(self._clients)} total)")
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                    self._handle_client_message(msg)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client: {raw[:100]}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info(f"Electron client disconnected ({len(self._clients)} remaining)")

    def _handle_client_message(self, msg: dict):
        """Process messages from the Electron frontend."""
        msg_type = msg.get("type", "")

        if msg_type == "start_task":
            task = msg.get("task", "")
            if task:
                self.orchestrator.start_task(task)

        elif msg_type == "stop":
            self.orchestrator.stop()

        elif msg_type == "confirm":
            approved = msg.get("approved", False)
            self.orchestrator.provide_confirmation(approved)

        elif msg_type == "pause":
            self.orchestrator.pause()

        elif msg_type == "resume":
            self.orchestrator.resume()

    def _on_agent_event(self, event_type: str, data: dict):
        """Called by the orchestrator whenever an event happens."""
        payload = json.dumps({"type": event_type, **data}, default=str)
        if self._loop and self._clients:
            asyncio.run_coroutine_threadsafe(
                self._broadcast(payload), self._loop
            )

    async def _broadcast(self, payload: str):
        """Send a message to all connected Electron clients."""
        if not self._clients:
            return
        dead = set()
        for client in self._clients:
            try:
                await client.send(payload)
            except Exception:
                dead.add(client)
        self._clients -= dead
