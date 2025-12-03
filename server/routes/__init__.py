"""Routes package"""
from routes.api import router as api_router
from routes.websockets import router as websocket_router

__all__ = ["api_router", "websocket_router"]

