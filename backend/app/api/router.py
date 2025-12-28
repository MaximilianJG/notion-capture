"""
Main API Router - Combines all route modules
"""
from fastapi import APIRouter

from .routes import capture, google, notion, health

# Create main router
api_router = APIRouter()

# Include all route modules
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(capture.router, tags=["Capture"])
api_router.include_router(google.router, prefix="/google", tags=["Google"])
api_router.include_router(notion.router, prefix="/notion", tags=["Notion"])

