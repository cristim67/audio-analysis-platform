"""WebSocket connection manager"""
from typing import Set

from fastapi import WebSocket

# Set of active WebSocket connections
active_connections: Set[WebSocket] = set()


def add_connection(websocket: WebSocket):
    """Add a WebSocket connection"""
    active_connections.add(websocket)


def remove_connection(websocket: WebSocket):
    """Remove a WebSocket connection"""
    active_connections.discard(websocket)


def get_connection_count() -> int:
    """Get number of active connections"""
    return len(active_connections)


async def broadcast_to_dashboards(message: str):
    """Broadcast message to all connected dashboards"""
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except:
            disconnected.add(connection)
    
    # Remove disconnected connections
    active_connections.difference_update(disconnected)

