"""WebSocket connection manager"""
from typing import Optional, Set

from fastapi import WebSocket

# Set of active WebSocket connections (dashboards)
active_connections: Set[WebSocket] = set()

# Arduino WebSocket connection (only one at a time)
arduino_connection: Optional[WebSocket] = None


def add_connection(websocket: WebSocket):
    """Add a WebSocket connection (dashboard)"""
    active_connections.add(websocket)


def remove_connection(websocket: WebSocket):
    """Remove a WebSocket connection (dashboard)"""
    active_connections.discard(websocket)


def set_arduino_connection(websocket: Optional[WebSocket]):
    """Set the Arduino WebSocket connection"""
    global arduino_connection
    arduino_connection = websocket


def get_arduino_connection() -> Optional[WebSocket]:
    """Get the Arduino WebSocket connection"""
    return arduino_connection


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


async def send_to_arduino(message: str) -> bool:
    """Send message to Arduino if connected"""
    if arduino_connection is None:
        return False
    
    try:
        await arduino_connection.send_text(message)
        return True
    except:
        return False

