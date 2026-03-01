"""WebSocket server for real-time dropped items streaming.

This module provides a WebSocket server that streams dropped items
from the overlay to connected web clients (dashboard).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Callable
import threading

logger = logging.getLogger(__name__)


@dataclass
class DroppedItem:
    """Represents a dropped item detected on ground."""
    id: str
    name: str
    base_type: str
    quality: str  # magic, rare, unique, set, etc.
    ilvl: int
    prefix: str | None
    suffix: str | None
    affixes: list[str]
    
    # Pricing
    estimated_fg: float
    tier: str  # gg, high, medium, low, trash
    color: str
    tag: str
    prefix_price: float
    suffix_price: float
    ilvl_multiplier: float
    is_lld: bool
    notes: str
    
    # Detection info
    detected_at: float
    screen_x: int = 0
    screen_y: int = 0
    tooltip_text: str = ""
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class GroundScanResult:
    """Result of scanning ground for items."""
    items: list[DroppedItem]
    total_value_fg: float
    gg_items_count: int
    high_items_count: int
    scan_time: float
    area_scanned: str = "full"
    
    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "total_value_fg": self.total_value_fg,
            "gg_items_count": self.gg_items_count,
            "high_items_count": self.high_items_count,
            "scan_time": self.scan_time,
            "area_scanned": self.area_scanned,
        }


class WebSocketServer:
    """Async WebSocket server for streaming dropped items."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: set = set()
        self._server = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        
        # Item history (last 100 items)
        self.item_history: list[DroppedItem] = []
        self.max_history = 100
        
        # Callbacks
        self._on_client_connect: Callable | None = None
        self._on_client_disconnect: Callable | None = None
    
    def start(self) -> None:
        """Start the WebSocket server in a background thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        logger.info(f"WebSocket server starting on {self.host}:{self.port}")
    
    def stop(self) -> None:
        """Stop the WebSocket server."""
        self._running = False
        if self._loop and self._server:
            # Schedule server close on the event loop
            asyncio.run_coroutine_threadsafe(self._close_server(), self._loop)
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("WebSocket server stopped")
    
    async def _close_server(self) -> None:
        """Close the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
    
    def _run_server(self) -> None:
        """Run the async server in this thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
        finally:
            self._loop.close()
    
    async def _serve(self) -> None:
        """Serve WebSocket connections."""
        import websockets
        
        async def handler(websocket, path):
            """Handle a WebSocket connection."""
            self.clients.add(websocket)
            client_addr = websocket.remote_address
            logger.info(f"Client connected: {client_addr}")
            
            if self._on_client_connect:
                self._on_client_connect(client_addr)
            
            try:
                # Send initial state
                await self._send_initial_state(websocket)
                
                # Keep connection alive, handle incoming messages
                async for message in websocket:
                    await self._handle_message(websocket, message)
                    
            except websockets.exceptions.ConnectionClosed:
                pass
            except Exception as e:
                logger.error(f"Error handling client {client_addr}: {e}")
            finally:
                self.clients.discard(websocket)
                logger.info(f"Client disconnected: {client_addr}")
                if self._on_client_disconnect:
                    self._on_client_disconnect(client_addr)
        
        self._server = await websockets.serve(handler, self.host, self.port)
        logger.info(f"WebSocket server listening on ws://{self.host}:{self.port}")
        
        # Keep running until stopped
        while self._running:
            await asyncio.sleep(0.1)
    
    async def _send_initial_state(self, websocket) -> None:
        """Send initial state to newly connected client."""
        state = {
            "type": "initial_state",
            "item_history": [item.to_dict() for item in self.item_history],
            "connected_at": time.time(),
        }
        await websocket.send(json.dumps(state))
    
    async def _handle_message(self, websocket, message: str) -> None:
        """Handle incoming message from client."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            if msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong", "time": time.time()}))
            elif msg_type == "get_history":
                await websocket.send(json.dumps({
                    "type": "item_history",
                    "items": [item.to_dict() for item in self.item_history]
                }))
            elif msg_type == "clear_history":
                self.item_history.clear()
                await self._broadcast({"type": "history_cleared"})
            elif msg_type == "request_scan":
                # Client requested a scan - emit event
                await websocket.send(json.dumps({
                    "type": "scan_requested",
                    "time": time.time()
                }))
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message: {message}")
    
    def broadcast_item(self, item: DroppedItem) -> None:
        """Broadcast a dropped item to all connected clients."""
        # Add to history
        self.item_history.append(item)
        if len(self.item_history) > self.max_history:
            self.item_history.pop(0)
        
        # Broadcast to all clients
        if self._loop and self.clients:
            message = {
                "type": "item_dropped",
                "item": item.to_dict(),
            }
            asyncio.run_coroutine_threadsafe(
                self._broadcast(message),
                self._loop
            )
    
    def broadcast_scan_result(self, result: GroundScanResult) -> None:
        """Broadcast a ground scan result to all clients."""
        # Add items to history
        for item in result.items:
            self.item_history.append(item)
        while len(self.item_history) > self.max_history:
            self.item_history.pop(0)
        
        # Broadcast
        if self._loop and self.clients:
            asyncio.run_coroutine_threadsafe(
                self._broadcast({
                    "type": "ground_scan",
                    "result": result.to_dict(),
                }),
                self._loop
            )
    
    def broadcast_clear(self) -> None:
        """Clear item history and notify clients."""
        self.item_history.clear()
        if self._loop and self.clients:
            asyncio.run_coroutine_threadsafe(
                self._broadcast({"type": "history_cleared"}),
                self._loop
            )
    
    async def _broadcast(self, message: dict) -> None:
        """Broadcast message to all connected clients."""
        if not self.clients:
            return
        
        message_json = json.dumps(message)
        disconnected = set()
        
        for client in self.clients:
            try:
                await client.send(message_json)
            except Exception:
                disconnected.add(client)
        
        # Remove disconnected clients
        self.clients -= disconnected
    
    def get_client_count(self) -> int:
        """Get number of connected clients."""
        return len(self.clients)
    
    def get_stats(self) -> dict:
        """Get server statistics."""
        return {
            "host": self.host,
            "port": self.port,
            "clients_connected": len(self.clients),
            "items_in_history": len(self.item_history),
            "running": self._running,
        }


# Singleton instance
_server_instance: WebSocketServer | None = None


def get_server(host: str = "localhost", port: int = 8765) -> WebSocketServer:
    """Get or create the WebSocket server singleton."""
    global _server_instance
    if _server_instance is None:
        _server_instance = WebSocketServer(host=host, port=port)
    return _server_instance
