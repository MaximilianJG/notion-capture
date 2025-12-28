# Notion Capture

A slim, single-purpose macOS menu bar application for quick capture. Events go to Google Calendar, everything else goes to Notion.

## How It Works

### 3-Part Pipeline

1. **Capture & Analyze**
   - Take a screenshot or type text
   - AI (GPT-4o Vision + OCR) analyzes the content
   - Determines if it's an event or something else

2. **Route & Enrich**
   - **Events** → Google Calendar (with date, time, location)
   - **Everything else** → Notion database (AI selects best match)
   - AI enriches empty properties by researching context (e.g., movie director, book author)

3. **Save & Summarize**
   - Creates the entry in the appropriate destination
   - Shows a "What AI Did" summary popup
   - Optionally logs activity to a Notion log database

## Features

- 📸 **Screenshot Capture**: Take screenshots with a global keyboard shortcut
- ⌨️ **Text Input**: Type directly to capture notes, tasks, etc.
- 🤖 **AI-Powered Analysis**: GPT-4o determines content type and extracts data
- 📅 **Google Calendar Integration**: Events automatically create calendar entries
- 📓 **Notion Integration**: Non-events go to your Notion databases
- 🔬 **AI Enrichment**: AI researches and fills missing database properties
- 📊 **Summary Popup**: See exactly what AI did after each capture
- 🎯 **No Persistent Storage**: All state is in-memory (resets on reload)

## Project Structure

```
notion-capture/
├── backend/              # FastAPI backend server
│   ├── main.py          # Main API endpoints
│   ├── services/
│   │   ├── ai.py        # OCR + GPT-4o analysis
│   │   ├── external.py  # Google Calendar OAuth
│   │   └── notion.py    # Notion OAuth and operations
│   ├── GOOGLE_SETUP.md  # Google OAuth setup guide
│   └── NOTION_SETUP.md  # Notion OAuth setup guide
└── mac/                 # macOS SwiftUI application
    └── notion-capture/  # Xcode project
```

## Prerequisites

- macOS (for the app)
- Python 3.8+ (for the backend)
- Google Cloud Project with Calendar API enabled
- Notion integration (public OAuth)
- OpenAI API key
- Xcode (for building the macOS app)

## Setup

### Backend Setup

1. **Create virtual environment and install dependencies:**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Google OAuth:**
   - Follow instructions in `backend/GOOGLE_SETUP.md`
   - Place `client_secret.json` in the `backend/` directory

3. **Configure Notion:**
   - Follow instructions in `backend/NOTION_SETUP.md`
   - Create a Notion Internal Integration and get the API token

4. **Create `.env` file:**
   ```bash
   # OpenAI
   OPENAI_API_KEY=your_openai_api_key
   
   # Notion (Internal Integration token)
   NOTION_API_KEY=secret_your_notion_token_here
   ```

5. **Share Notion pages with your integration:**
   - In Notion, go to the page with your databases
   - Click "..." → "Connections" → Add your integration

6. **Start the backend server:**
   ```bash
   cd backend
   source .venv/bin/activate  # If not already activated
   uvicorn main:app --reload
   ```
   The server will run on `http://localhost:8000`

### macOS App Setup

1. **Open the project in Xcode:**
   ```bash
   open mac/notion-capture/notion-capture.xcodeproj
   ```

2. **Build and run:**
   - Select your development team in Xcode
   - Build and run the project (⌘R)

3. **Grant permissions:**
   - **Accessibility**: Required for global keyboard shortcuts
     - System Settings → Privacy & Security → Accessibility
   - **Screen Recording**: Required for screenshots
     - System Settings → Privacy & Security → Screen Recording

## Usage

1. **Connect Google Calendar:**
   - Open the app and go to Configure tab
   - Click "Connect to Google Calendar" and complete OAuth
   - Notion connects automatically if `NOTION_API_KEY` is set

2. **Capture:**
   - Press your keyboard shortcut (default: ⌘⇧S) to screenshot
   - Or type in the text field and press Enter/Send
   - AI analyzes and routes to the right destination

3. **View Results:**
   - A popup shows what AI did (database, filled properties, etc.)
   - Recent captures show in the Home tab

## API Endpoints

### Capture
- `POST /upload-screenshot` - Upload and process screenshot
- `POST /process-text` - Process text input

### Google Auth
- `GET /google/auth/status` - Check connection status
- `GET /google/auth/url` - Get OAuth URL
- `GET /google/auth/callback` - OAuth callback
- `POST /google/auth/logout` - Disconnect

### Notion
- `GET /notion/auth/status` - Check connection status (uses NOTION_API_KEY)
- `GET /notion/pages` - List accessible pages
- `GET /notion/databases` - List databases
- `GET /notion/databases/{id}/properties` - Get database schema

### Other
- `GET /health` - Health check
- `GET /logs` - Get session activity log

## Log Database Detection

If you have a Notion database with "log" in its name, the app will automatically write activity logs there. Logs include:

- Action performed (Create Event, Create Page, etc.)
- Timestamp
- Result (Success/Failed)
- Target database name
- Details about what was filled

To enable logging:
1. Create a database named "Log" or "Activity Log" in your shared Notion page
2. Add properties: Name (title), Timestamp (date), Result (select/text), Database (text), Details (text)
3. The app will auto-detect and use it

## Architecture Notes

- **No Persistent Storage**: The app stores nothing locally except OAuth tokens. All capture data goes directly to Google Calendar or Notion.
- **In-Memory Session Log**: Activity logs are kept in memory and reset when the server restarts.
- **Token Persistence**: OAuth tokens are saved to files (`token.pickle` for Google, `notion_token.json` for Notion) so you don't have to re-authenticate on restart.

## Development

### Backend
- FastAPI with async support
- Google Calendar API integration
- Notion API integration with OAuth
- OpenAI GPT-4o for analysis

### Frontend
- SwiftUI for macOS
- Menu bar integration
- Global keyboard shortcuts (Carbon Hotkeys)
- Background operation support

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
