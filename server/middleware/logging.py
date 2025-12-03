"""Request logging middleware"""
from datetime import datetime

from fastapi import Request


async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {request.method} {request.url.path}")
    response = await call_next(request)
    print(f"  Status: {response.status_code}\n")
    return response

