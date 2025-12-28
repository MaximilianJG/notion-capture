"""
Notion Capture API - Stateless Multi-User Backend

Architecture:
- Stateless: No stored credentials, all passed per request
- Multi-user: Frontend sends credentials, backend processes
- BYOC: Bring Your Own Credentials

Flow:
1. Capture → AI Analysis
2. Route: Events → Google Calendar, Other → Notion
"""
import os
import ssl
import warnings

# Fix SSL certificate issues on macOS - disable verification for development
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'

# Suppress SSL warnings in development
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Also try certifi if available
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except ImportError:
    pass

# Monkey-patch httpx to disable SSL verification (for development)
import httpx
_original_client_init = httpx.Client.__init__
def _patched_client_init(self, *args, **kwargs):
    kwargs['verify'] = False
    _original_client_init(self, *args, **kwargs)
httpx.Client.__init__ = _patched_client_init

_original_async_client_init = httpx.AsyncClient.__init__
def _patched_async_client_init(self, *args, **kwargs):
    kwargs['verify'] = False
    _original_async_client_init(self, *args, **kwargs)
httpx.AsyncClient.__init__ = _patched_async_client_init

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
print("🔧 Loading environment variables...", flush=True)
from dotenv import load_dotenv
load_dotenv()
print("✅ Environment variables loaded", flush=True)

# Import router
from app.api.router import api_router

# Create app
print("🔧 Creating FastAPI app...", flush=True)
app = FastAPI(
    title="Notion Capture API",
    version="4.0.0",
    description="Stateless multi-user capture flow: Events → Google Calendar, Everything else → Notion"
)
print("✅ FastAPI app created", flush=True)

# CORS middleware - allow all origins for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    print("🚀 FastAPI server started!", flush=True)
    print("🌐 API available at http://127.0.0.1:8000", flush=True)
    print("📚 API docs available at http://127.0.0.1:8000/docs", flush=True)
    print("")
    print("📋 Stateless Backend - Credentials sent per request", flush=True)
    print("   Frontend stores: Notion API Key, Google OAuth Tokens", flush=True)
    print("")

