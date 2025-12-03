"""API routes"""
from pathlib import Path

from config.settings import DB_PATH, STATIC_DIR
from database.db import get_total_records
from fastapi import APIRouter
from fastapi.responses import FileResponse
from models.schemas import (
    ApiInfoResponse,
    HealthResponse,
    LatestDataResponse,
    StatsResponse,
)
from services.storage import get_latest_data, get_latest_data_count
from services.websocket_manager import get_connection_count

router = APIRouter()


@router.get("/", response_model=ApiInfoResponse)
async def home():
    """Serve dashboard HTML or return API info"""
    dashboard_path = STATIC_DIR / "index.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    return {
        "message": "IoT WebSocket Server",
        "websocket": "/ws",
        "dashboard": "/ws-dashboard",
        "static_files": "/static",
        "dashboard_url": "/static/index.html",
        "status": "running"
    }


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    from datetime import datetime
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "active_connections": get_connection_count(),
        "latest_data_count": get_latest_data_count()
    }


@router.get("/data/latest", response_model=LatestDataResponse)
async def get_latest_data_route(count: int = 10):
    """Get latest N data points (for HTTP dashboard)"""
    data = get_latest_data(count)
    return {
        "count": len(data),
        "data": data
    }


@router.get("/data/stats", response_model=StatsResponse)
async def get_stats():
    """Statistics about saved data"""
    try:
        total = await get_total_records()
        db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        
        return {
            "total_records": total,
            "db_size_kb": round(db_size / 1024, 2),
            "latest_data_count": get_latest_data_count(),
            "active_dashboard_connections": get_connection_count()
        }
    except Exception as e:
        return {"error": str(e)}

