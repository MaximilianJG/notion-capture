"""
Health and root endpoints
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    """Root endpoint - API information"""
    return {
        "name": "Notion Capture API",
        "version": "4.0.0",
        "description": "Stateless multi-user capture flow: Events → Google Calendar, Everything else → Notion",
        "architecture": {
            "ai": "GPT-4o Vision + OCR",
            "calendar": "Google Calendar",
            "storage": "Notion",
            "auth": "Frontend stores credentials (BYOC)"
        },
        "endpoints": {
            "health": "/health",
            "capture": "/upload-screenshot, /process-text",
            "google": "/google/auth/*",
            "notion": "/notion/*"
        }
    }


@router.get("/health")
def health():
    """Health check endpoint"""
    return {"ok": True}

