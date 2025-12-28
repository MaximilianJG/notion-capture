# Notion Capture

A macOS menu bar app that captures screenshots and text, analyzes them with AI, and routes them to Google Calendar (events) or Notion (everything else).

## Architecture

**Stateless Multi-User Backend** with **BYOC (Bring Your Own Credentials)**

- **Frontend** stores all credentials locally (Notion API key, Google OAuth tokens)
- **Backend** is stateless - receives credentials with each request
- **Multi-user ready** - deploy once, each user brings their own credentials

```
┌─────────────────────┐         ┌─────────────────────┐
│   macOS App         │         │   Backend API       │
│   (SwiftUI)         │ ──────► │   (FastAPI)         │
│                     │         │                     │
│ • Stores credentials│         │ • Stateless         │
│ • Sends with request│         │ • AI Analysis       │
│ • Shows results     │         │ • Routes to dest    │
└─────────────────────┘         └─────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
            ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
            │   OpenAI      │   │   Google      │   │   Notion      │
            │   GPT-4o      │   │   Calendar    │   │   API         │
            └───────────────┘   └───────────────┘   └───────────────┘
```

## Features

- **Screenshot Capture** - Select a region, AI extracts and analyzes content
- **Text Input** - Type anything, AI categorizes and routes it
- **AI Analysis** - GPT-4o Vision for screenshots, GPT-4o for text
- **Smart Routing**:
  - Events with date+time → Google Calendar
  - Everything else → Best-matching Notion database
- **AI Enrichment** - Fills in factual properties (director, year, etc.)
- **Local Credentials** - Your API keys stay on your device

## Backend Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, startup
│   ├── config.py            # Settings from env
│   │
│   ├── api/                 # HTTP routes
│   │   ├── router.py        # Combines all routes
│   │   └── routes/
│   │       ├── capture.py   # /process-text, /upload-screenshot
│   │       ├── google.py    # /google/auth/*
│   │       ├── notion.py    # /notion/*
│   │       └── health.py    # /, /health
│   │
│   ├── schemas/             # Pydantic models
│   │   ├── capture.py       # TextInput, CaptureResult
│   │   ├── credentials.py   # NotionCredentials, GoogleCredentials
│   │   ├── google.py        # GoogleAuthStatus
│   │   └── notion.py        # NotionDatabase, NotionPage
│   │
│   ├── services/            # Business logic
│   │   ├── capture.py       # Orchestration
│   │   ├── ai/              # AI operations
│   │   │   ├── analyzer.py  # OCR + GPT-4o analysis
│   │   │   ├── database_selector.py
│   │   │   ├── property_mapper.py
│   │   │   └── enricher.py
│   │   ├── google/          # Google Calendar
│   │   │   ├── auth.py      # OAuth flow
│   │   │   └── calendar.py  # Event CRUD
│   │   └── notion/          # Notion API
│   │       ├── client.py    # API client
│   │       ├── pages.py     # Page operations
│   │       ├── databases.py # Database operations
│   │       └── properties.py # Property builders
│   │
│   └── core/                # Shared utilities
│       ├── datetime_utils.py
│       ├── openai_client.py
│       └── logging.py
│
├── run.py                   # Entry point
└── requirements.txt
```

## Setup

### Prerequisites

- Python 3.11+
- macOS (for the frontend app)
- Tesseract OCR: `brew install tesseract`

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
OPENAI_API_KEY=sk-your-openai-api-key
EOF

# Run the server
python run.py
```

### Frontend Setup

1. Open `mac/notion-capture/notion-capture.xcodeproj` in Xcode
2. Build and run (⌘R)
3. The app appears in your menu bar

### Connecting Services

#### Notion
1. Go to [notion.so/my-integrations](https://notion.so/my-integrations)
2. Create a new Internal Integration
3. Copy the API key
4. In the app, go to Configure → Notion → paste your API key
5. Share your Notion pages/databases with the integration

#### Google Calendar
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create OAuth 2.0 credentials
3. Download `client_secret.json` to `backend/`
4. In the app, click "Connect to Google Calendar"
5. Complete the OAuth flow in your browser

## API Endpoints

### Capture
- `POST /process-text` - Process text input
- `POST /upload-screenshot` - Process screenshot

### Google
- `GET /google/auth/status` - Check connection status
- `GET /google/auth/url` - Get OAuth URL
- `GET /google/auth/callback` - OAuth callback
- `POST /google/test-event` - Create test event

### Notion
- `GET /notion/auth/status` - Check connection status
- `GET /notion/pages` - List pages
- `GET /notion/databases` - List databases

### Headers for Credentials

All endpoints accept credentials via headers:
- `X-Notion-Api-Key` - Notion Internal Integration API key
- `X-Notion-Page-Id` - Selected Notion page ID (optional)
- `X-Google-Tokens` - JSON string of Google OAuth tokens

## Development

### Running Locally

```bash
# Terminal 1: Backend
cd backend && source .venv/bin/activate && python run.py

# Terminal 2: Frontend (via Xcode or)
open mac/notion-capture/notion-capture.xcodeproj
```

### Deploying Backend

The backend is stateless and can be deployed to any cloud provider:

```bash
# Example with Railway/Render/Fly.io
# Just set OPENAI_API_KEY environment variable
# Frontend connects to deployed URL instead of localhost
```

## License

MIT
