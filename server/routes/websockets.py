"""WebSocket routes"""
import asyncio
import json
from datetime import datetime

from config.settings import (
    DASHBOARD_INITIAL_DATA_COUNT,
    FLUSH_INTERVAL_SECONDS,
    SQLITE_BUFFER_SIZE,
)
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.storage import add_sensor_data, flush_sqlite_buffer, get_latest_data
from services.websocket_manager import (
    add_connection,
    broadcast_to_dashboards,
    get_connection_count,
    remove_connection,
)

router = APIRouter()


@router.websocket("/ws")
async def websocket_arduino(websocket: WebSocket):
    """
    WebSocket endpoint for Arduino.
    Receives data from Arduino and saves it + sends to dashboards.
    """
    client_host = websocket.client.host if websocket.client else "Unknown"
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔌 Arduino connection from {client_host}")
    
    try:
        await websocket.accept()
        print(f"  ✅ Arduino CONNECTED from {client_host}")
        await websocket.send_text('{"status":"connected","message":"Welcome!"}')
        
        # Task for periodic flush of SQLite buffer (non-blocking)
        async def periodic_flush():
            while True:
                await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
                # Run in background, don't block
                asyncio.create_task(flush_sqlite_buffer())
        
        flush_task = asyncio.create_task(periodic_flush())
        
        try:
            while True:
                data = await websocket.receive_text()
                print(f"  📨 Received from Arduino: {data}")
                
                try:
                    data_json = json.loads(data)
                    data_json["timestamp"] = datetime.now().isoformat()
                    data_json["client"] = client_host
                    data_json["source"] = "arduino"
                    
                    # Add to storage (memory + buffer)
                    add_sensor_data(data_json)
                    
                    # Broadcast to all dashboards
                    await broadcast_to_dashboards(json.dumps(data_json))
                    
                except json.JSONDecodeError:
                    print(f"  ⚠️  Invalid JSON message: {data}")
                
                # Echo response
                await websocket.send_text(f"Echo: {data}")
                
        finally:
            flush_task.cancel()
            # Save remaining buffer (non-blocking)
            from services.storage import sqlite_buffer
            if sqlite_buffer:
                asyncio.create_task(flush_sqlite_buffer())
            
    except WebSocketDisconnect:
        print(f"  ❌ Arduino DISCONNECTED from {client_host}")
    except Exception as e:
        print(f"  ⚠️ WebSocket ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


@router.websocket("/ws-dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    WebSocket endpoint for Dashboard.
    Receives real-time updates from Arduino.
    """
    client_host = websocket.client.host if websocket.client else "Unknown"
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📊 Dashboard connection from {client_host}")
    
    try:
        await websocket.accept()
        add_connection(websocket)
        print(f"  ✅ Dashboard CONNECTED from {client_host} (Total: {get_connection_count()})")
        
        # Send latest available data immediately
        latest = get_latest_data(DASHBOARD_INITIAL_DATA_COUNT)
        if latest:
            initial_data = {
                "type": "initial_data",
                "data": latest
            }
            await websocket.send_text(json.dumps(initial_data))
        
        # Wait for messages from dashboard (for future commands)
        while True:
            try:
                data = await websocket.receive_text()
                print(f"  📥 Received from Dashboard: {data}")
                
                # Here you can process commands from dashboard
                # (e.g., send command to Arduino through another channel)
                
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        print(f"  ❌ Dashboard DISCONNECTED from {client_host}")
    except Exception as e:
        print(f"  ⚠️ Dashboard ERROR: {type(e).__name__}: {e}")
    finally:
        remove_connection(websocket)
        print(f"  📊 Active dashboards: {get_connection_count()}")

