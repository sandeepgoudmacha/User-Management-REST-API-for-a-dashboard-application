"""WebSocket support for real-time availability checking."""

from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json
import asyncio
import uuid
from app.providers.base import ProviderResult


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.check_sessions: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and store WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        await self.send_personal_message(
            {"type": "connected", "client_id": client_id},
            client_id
        )

    def disconnect(self, client_id: str):
        """Remove WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.check_sessions:
            del self.check_sessions[client_id]

    async def send_personal_message(self, message: dict, client_id: str):
        """Send message to specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except:
                pass

    async def start_check_session(self, client_id: str, name: str, providers: list):
        """Initialize a new checking session."""
        session_id = str(uuid.uuid4())
        total_checks = self._calculate_total_checks(providers)

        self.check_sessions[client_id] = {
            "session_id": session_id,
            "name": name,
            "providers": providers,
            "started_at": datetime.utcnow().isoformat(),
            "total_checks": total_checks,
            "completed_checks": 0,
            "results": {}
        }

        await self.send_personal_message({
            "type": "session_started",
            "session_id": session_id,
            "name": name,
            "total_checks": total_checks
        }, client_id)

        return session_id

    async def update_check_progress(
        self,
        client_id: str,
        provider_category: str,
        provider_name: str,
        result: ProviderResult
    ):
        """Update progress for ongoing check."""
        if client_id not in self.check_sessions:
            return

        session = self.check_sessions[client_id]

        # Store result
        if provider_category not in session["results"]:
            session["results"][provider_category] = {}

        session["results"][provider_category][provider_name] = {
            "available": result.available,
            "checked_at": result.checked_at.isoformat() if result.checked_at else None
        }

        session["completed_checks"] += 1
        progress_percentage = (session["completed_checks"] / session["total_checks"]) * 100

        # Send progress update
        await self.send_personal_message({
            "type": "progress_update",
            "session_id": session["session_id"],
            "provider": f"{provider_category}.{provider_name}",
            "result": {
                "available": result.available,
                "status": "success" if result.available is not None else "error"
            },
            "progress": {
                "completed": session["completed_checks"],
                "total": session["total_checks"],
                "percentage": round(progress_percentage, 1)
            }
        }, client_id)

    async def complete_check_session(self, client_id: str, summary: dict):
        """Mark session as complete and send final results."""
        if client_id not in self.check_sessions:
            return

        session = self.check_sessions[client_id]

        await self.send_personal_message({
            "type": "session_complete",
            "session_id": session["session_id"],
            "name": session["name"],
            "summary": summary,
            "results": session["results"],
            "duration_ms": self._calculate_duration(session["started_at"])
        }, client_id)

        # Clean up session
        del self.check_sessions[client_id]

    def _calculate_total_checks(self, providers: list) -> int:
        """Calculate total number of checks based on providers."""
        # Rough estimation - actual count depends on enabled providers
        provider_counts = {
            "domains": 10,
            "social": 8,
            "package_registries": 5,
            "app_stores": 3,
            "dev_platforms": 5
        }
        return sum(provider_counts.get(p, 5) for p in providers)

    def _calculate_duration(self, started_at: str) -> int:
        """Calculate duration in milliseconds."""
        start = datetime.fromisoformat(started_at)
        duration = datetime.utcnow() - start
        return int(duration.total_seconds() * 1000)


# Global connection manager instance
manager = ConnectionManager()


class RealtimeChecker:
    """Handles real-time availability checking with WebSocket updates."""

    def __init__(self, connection_manager: ConnectionManager):
        self.manager = connection_manager

    async def check_with_updates(
        self,
        client_id: str,
        name: str,
        providers: list,
        check_function
    ):
        """Perform availability check with real-time updates."""
        # Start session
        session_id = await self.manager.start_check_session(client_id, name, providers)

        try:
            # Create a custom callback for progress updates
            async def progress_callback(category: str, provider: str, result: ProviderResult):
                await self.manager.update_check_progress(
                    client_id, category, provider, result
                )

            # Perform the actual check with progress callbacks
            result = await check_function(
                name=name,
                providers=providers,
                progress_callback=progress_callback
            )

            # Send completion
            await self.manager.complete_check_session(client_id, result.summary.dict())

            return result

        except Exception as e:
            # Send error message
            await self.manager.send_personal_message({
                "type": "error",
                "session_id": session_id,
                "error": str(e)
            }, client_id)
            raise