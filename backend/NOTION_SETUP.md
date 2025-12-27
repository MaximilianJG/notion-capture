# Notion Integration Setup Guide

This guide explains how to set up Notion for the Notion Capture app using an **Internal Integration** (simple API token).

## Quick Setup (5 minutes)

### 1. Create a Notion Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Fill in:
   - **Name**: "Notion Capture" (or any name you like)
   - **Associated workspace**: Select your workspace
   - **Type**: Keep as **"Internal"** (default)
4. Click **"Submit"**

### 2. Copy the API Token

1. After creating, you'll see the **"Internal Integration Secret"**
2. Click **"Show"** then **"Copy"**
3. It looks like: `secret_abc123xyz...`

### 3. Add to Environment

Add this line to your `.env` file in the `backend/` directory:

```bash
NOTION_API_KEY=secret_your_token_here
```

### 4. Share Pages with the Integration

**Important:** Your integration can only access pages you explicitly share with it.

1. Open Notion and go to the page containing your databases
2. Click the **"..."** menu (top right)
3. Click **"Connections"** (or "Add connections")
4. Search for and select your integration ("Notion Capture")
5. Click **"Confirm"**

Repeat for any pages/databases you want the app to access.

### 5. Restart the Backend

```bash
# Stop the server (Ctrl+C) and restart
uvicorn main:app --reload
```

The app should now show "Notion connected" in the Configure tab!

## How It Works

### Database Discovery
When connected, the app searches for all databases you've shared with the integration and caches them for quick access.

### Automatic Database Selection  
When you capture something (screenshot or text), AI analyzes the content and selects the most appropriate database based on:
- Database name matching (e.g., "Movies" database for movie captures)
- Property name matching
- Content type detection

### Property Mapping
User data is automatically mapped to database properties by name similarity:
- "title" → Name/Title property
- "description" → Description/Notes property
- Dates → Date properties
- etc.

### AI Enrichment
For empty "researchable" properties (like director, author, genre), AI can fill them by inferring from context. For example:
- Movie title → Director, Year, Genre
- Book title → Author, Publisher

### Log Database
If you have a database with "log" in its name, the app automatically writes activity logs there.

## Troubleshooting

### "Notion not connected (NOTION_API_KEY not set)"
Make sure `NOTION_API_KEY` is set in your `.env` file and restart the backend.

### "Invalid API key"
Double-check that you copied the full token (starts with `secret_`).

### "No databases found"
You need to share pages with your integration:
1. Go to the Notion page with your databases
2. Click "..." → "Connections" → Add your integration

### "Failed to create page"
Check that:
1. The database has been shared with the integration
2. The database has a title/name property
3. Your integration has "Insert content" capability (enabled by default)

## Capabilities

Your integration needs these capabilities (all enabled by default):
- ✅ Read content
- ✅ Update content
- ✅ Insert content

You can verify/modify these at [notion.so/my-integrations](https://www.notion.so/my-integrations) → Select your integration → "Capabilities"

## Migrating to Public Integration (OAuth)

If you later want to distribute this app to other users, you can add OAuth:

1. Change integration type to "Public" in Notion
2. Set up OAuth redirect URIs (requires HTTPS)
3. Add OAuth endpoints to the backend
4. The API calls remain exactly the same - only the token source changes

For personal use, the Internal Integration is simpler and works great!
