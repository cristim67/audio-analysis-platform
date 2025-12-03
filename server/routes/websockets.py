"""WebSocket routes"""
import asyncio
import json
import struct
from datetime import datetime

from config.logger import logger
from config.settings import DASHBOARD_INITIAL_DATA_COUNT
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.storage import add_sensor_data, get_latest_data
from services.websocket_manager import (
    add_connection,
    broadcast_to_dashboards,
    get_connection_count,
    remove_connection,
    send_binary_to_arduino,
    send_to_arduino,
    set_arduino_connection,
)

router = APIRouter()


@router.websocket("/ws")
async def websocket_arduino(websocket: WebSocket):
    """
    WebSocket endpoint for Arduino and laptop microphone.
    Receives data from both sources and saves it + sends to dashboards.
    """
    client_host = websocket.client.host if websocket.client else "Unknown"
    logger.info(f"WebSocket connection attempt from {client_host}")
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket CONNECTED from {client_host}")
        await websocket.send_text('{"status":"connected","message":"Welcome!"}')
        
        # Determine if this is Arduino or laptop microphone based on first message
        is_arduino_connection = None
        
        # Heartbeat task to keep connection alive (important for ngrok)
        async def heartbeat():
            """Send periodic heartbeat to keep connection alive"""
            try:
                while True:
                    await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                    try:
                        await websocket.send_text('{"type":"heartbeat","timestamp":"' + datetime.now().isoformat() + '"}')
                    except:
                        break
            except asyncio.CancelledError:
                pass
        
        heartbeat_task = asyncio.create_task(heartbeat())
        
        try:
            while True:
                # Receive both text and binary messages
                message = await websocket.receive()
                
                # Check for disconnect message
                if message.get("type") == "websocket.disconnect":
                    logger.info(f"Client {client_host} disconnected gracefully")
                    break
                
                # Handle binary message (FAST path - from laptop microphone)
                if "bytes" in message:
                    binary_data = message["bytes"]
                    logger.debug(f"📦 Received BINARY data: {len(binary_data)} bytes from {client_host}")
                    
                    # Binary protocol header (8 bytes):
                    # - Byte 0: Message type (0x01 = audio from laptop)
                    # - Bytes 1-4: Timestamp (uint32)
                    # - Bytes 5-6: Sample rate / 100
                    # - Byte 7: Chunk size / 64
                    if len(binary_data) >= 8:
                        msg_type = binary_data[0]
                        
                        if msg_type == 0x01:  # Laptop microphone audio
                            # Forward binary directly to Arduino (FAST - no JSON!)
                            forwarded = await send_binary_to_arduino(binary_data)
                            if not forwarded:
                                logger.warning("⚠️ Arduino not connected - binary data not forwarded")
                            
                            # Also create JSON for dashboard (less frequent)
                            # Parse header for dashboard display
                            # Format: B (1) + I (4) + H (2) + B (1) = 8 bytes
                            _, timestamp, rate_div, chunk_div = struct.unpack('<BIHB', binary_data[:8])
                            audio_bytes = binary_data[8:]
                            
                            # Store minimal info for dashboard
                            data_json = {
                                "source": "laptop_microphone",
                                "timestamp": datetime.now().isoformat(),
                                "client": client_host,
                                "rate": rate_div * 100,
                                "chunk_size": chunk_div * 64,
                                "audio_length": len(audio_bytes)
                            }
                            add_sensor_data(data_json)
                            # Broadcast to dashboards (without audio data - too big)
                            await broadcast_to_dashboards(json.dumps(data_json))
                    continue
                
                # Handle text message (JSON - from Arduino or legacy)
                if "text" not in message:
                    # Not binary, not text - might be disconnect or other control message
                    if "bytes" not in message:
                        logger.debug(f"Unknown message type from {client_host}: {message.get('type', 'unknown')}")
                    continue
                    
                data = message["text"]
                logger.info(f"Received from client [{client_host}]: {data[:100]}...")
                
                try:
                    data_json = json.loads(data)
                    
                    # Handle Arduino request for audio data
                    if data_json.get("request") == "audio_data":
                        # Arduino requests are handled - binary data is streamed automatically
                        logger.debug(f"Arduino requested audio data")
                        continue
                    
                    data_json["timestamp"] = datetime.now().isoformat()
                    data_json["client"] = client_host
                    
                    # Determine source from message
                    if "source" in data_json:
                        source = data_json["source"]
                        if source == "laptop_microphone":
                            # This is laptop microphone - don't set as Arduino connection
                            data_json["source"] = "laptop_microphone"
                            is_arduino_connection = False
                        else:
                            # This is Arduino
                            data_json["source"] = "arduino"
                            if is_arduino_connection is None:
                                is_arduino_connection = True
                                set_arduino_connection(websocket)
                                logger.info(f"🤖 Arduino connected and registered from {client_host}")
                    else:
                        # Default to arduino if no source specified
                        if "source" not in data_json:
                            data_json["source"] = "arduino"
                        if is_arduino_connection is None:
                            is_arduino_connection = True
                            set_arduino_connection(websocket)
                    
                    # Add to storage (memory only)
                    add_sensor_data(data_json)
                    
                    # Broadcast to all dashboards
                    await broadcast_to_dashboards(json.dumps(data_json))
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON message from {client_host}: {data[:100]}")
                
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            if is_arduino_connection:
                set_arduino_connection(None)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket DISCONNECTED from {client_host} (normal disconnect)")
        set_arduino_connection(None)
    except RuntimeError as e:
        # Handle "Cannot call receive once disconnected" gracefully
        if "disconnect" in str(e).lower():
            logger.info(f"WebSocket {client_host} disconnected (runtime)")
        else:
            logger.error(f"WebSocket RuntimeError from {client_host}: {e}")
        set_arduino_connection(None)
    except Exception as e:
        logger.error(f"WebSocket ERROR from {client_host}: {type(e).__name__}: {e}")
        set_arduino_connection(None)


@router.websocket("/ws-microphone")
async def websocket_microphone(websocket: WebSocket):
    """
    WebSocket endpoint for laptop microphone client.
    Receives audio data from laptop and forwards it to Arduino.
    """
    client_host = websocket.client.host if websocket.client else "Unknown"
    logger.info(f"Microphone client connection attempt from {client_host}")
    
    try:
        await websocket.accept()
        logger.info(f"Microphone client CONNECTED from {client_host}")
        
        # Send welcome message immediately to keep connection alive
        await websocket.send_text('{"status":"connected","message":"Welcome! Microphone endpoint ready."}')
        
        # Heartbeat task to keep connection alive (important for ngrok)
        async def heartbeat():
            """Send periodic heartbeat to keep connection alive"""
            try:
                while True:
                    await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                    try:
                        await websocket.send_text('{"type":"heartbeat","timestamp":"' + datetime.now().isoformat() + '"}')
                    except:
                        break
            except asyncio.CancelledError:
                pass
        
        heartbeat_task = asyncio.create_task(heartbeat())
        
        # Counter for logging (reduce spam)
        binary_count = 0
        
        try:
            while True:
                # Receive both text and binary messages
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=60.0)
                    
                    # Check for disconnect message
                    if message.get("type") == "websocket.disconnect":
                        logger.info(f"Microphone client {client_host} disconnected gracefully")
                        break
                    
                    # Handle BINARY message (FAST path - new protocol)
                    if "bytes" in message:
                        binary_data = message["bytes"]
                        binary_count += 1
                        
                        # Log every 100th packet to avoid spam
                        if binary_count % 100 == 0:
                            logger.info(f"📦 Binary audio #{binary_count}: {len(binary_data)} bytes from {client_host}")
                        
                        # Forward binary directly to Arduino (FAST - no JSON parsing!)
                        forwarded = await send_binary_to_arduino(binary_data)
                        if not forwarded and binary_count % 100 == 0:
                            logger.warning(f"⚠️ Arduino not connected - binary not forwarded")
                        
                        # Parse header for dashboard (optional, minimal data)
                        if len(binary_data) >= 8:
                            _, timestamp, rate_div, chunk_div = struct.unpack('<BIHB', binary_data[:8])
                            audio_length = len(binary_data) - 8
                            
                            # Minimal dashboard update (every 10th packet)
                            if binary_count % 10 == 0:
                                data_json = {
                                    "source": "laptop_microphone",
                                    "timestamp": datetime.now().isoformat(),
                                    "client": client_host,
                                    "rate": rate_div * 100,
                                    "chunk_size": chunk_div * 64,
                                    "audio_length": audio_length,
                                    "packet_count": binary_count
                                }
                                add_sensor_data(data_json)
                                asyncio.create_task(broadcast_to_dashboards(json.dumps(data_json)))
                        continue
                    
                    # Handle TEXT message (legacy JSON protocol)
                    if "text" in message:
                        data = message["text"]
                        logger.info(f"Received TEXT from microphone [{client_host}]: {data[:100]}...")
                        
                        try:
                            data_json = json.loads(data)
                            data_json["timestamp"] = datetime.now().isoformat()
                            data_json["client"] = client_host
                            data_json["source"] = "laptop_microphone"
                            
                            add_sensor_data(data_json)
                            asyncio.create_task(broadcast_to_dashboards(json.dumps(data_json)))
                            
                            # Forward JSON to Arduino (legacy)
                            await send_to_arduino(data)
                            
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON from microphone [{client_host}]: {data[:100]}")
                        continue
                        
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    try:
                        await websocket.send_text('{"type":"heartbeat","timestamp":"' + datetime.now().isoformat() + '"}')
                        logger.debug(f"Heartbeat sent to microphone client [{client_host}]")
                    except:
                        break
                
        except WebSocketDisconnect:
            logger.info(f"Microphone client DISCONNECTED from {client_host}")
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            
    except WebSocketDisconnect:
        logger.info(f"Microphone client DISCONNECTED from {client_host}")
    except RuntimeError as e:
        # Handle "Cannot call receive once disconnected" gracefully
        if "disconnect" in str(e).lower():
            logger.info(f"Microphone client {client_host} disconnected (runtime)")
        else:
            logger.error(f"Microphone client RuntimeError from {client_host}: {e}")
    except Exception as e:
        logger.error(f"Microphone client ERROR from {client_host}: {type(e).__name__}: {e}")


@router.websocket("/ws-dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    WebSocket endpoint for Dashboard.
    Receives real-time updates from Arduino.
    """
    client_host = websocket.client.host if websocket.client else "Unknown"
    logger.info(f"Dashboard connection attempt from {client_host}")
    
    try:
        await websocket.accept()
        add_connection(websocket)
        logger.info(f"Dashboard CONNECTED from {client_host} (Total: {get_connection_count()})")
        
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
                logger.info(f"Received from Dashboard [{client_host}]: {data}")
                
                # Here you can process commands from dashboard
                # (e.g., send command to Arduino through another channel)
                
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        logger.info(f"Dashboard DISCONNECTED from {client_host}")
    except Exception as e:
        logger.error(f"Dashboard ERROR from {client_host}: {type(e).__name__}: {e}", exc_info=True)
    finally:
        remove_connection(websocket)
        logger.info(f"Active dashboards: {get_connection_count()}")

