"""Storage service for managing sensor data buffer"""
import asyncio
from collections import deque
from typing import Dict

from config.settings import LATEST_DATA_MAX_SIZE, SQLITE_BUFFER_SIZE
from database.db import save_sensor_data_batch

# Buffer for batch writes to SQLite
sqlite_buffer: list = []

# In-memory storage for dashboard (latest N values)
latest_data: deque = deque(maxlen=LATEST_DATA_MAX_SIZE)


async def flush_sqlite_buffer():
    """Flush buffer to SQLite (completely async)"""
    global sqlite_buffer
    if not sqlite_buffer:
        return
    
    # Copy buffer and clear immediately (don't wait for save)
    buffer_copy = sqlite_buffer.copy()
    sqlite_buffer.clear()
    
    # Save asynchronously
    await save_sensor_data_batch(buffer_copy)


def add_sensor_data(data: Dict):
    """Add sensor data to memory and buffer"""
    # 1. Save to memory (for dashboard)
    latest_data.append(data)
    
    # 2. Add to SQLite buffer
    sqlite_buffer.append(data)
    
    # 3. Flush if buffer is full (non-blocking)
    if len(sqlite_buffer) >= SQLITE_BUFFER_SIZE:
        asyncio.create_task(flush_sqlite_buffer())


def get_latest_data(count: int = 10) -> list:
    """Get latest N data points"""
    return list(latest_data)[-count:]


def get_latest_data_count() -> int:
    """Get count of latest data"""
    return len(latest_data)

