# Notion Integration Setup Guide

This guide explains how to set up Notion for the Notion Capture app. You can use either:
- **Public Integration (OAuth)** - Recommended for distribution. Users click "Connect to Notion" and authorize.
- **Internal Integration (API Key)** - Simpler for personal use. Users paste their API key.

---

## Option 1: Public Integration (OAuth) - Recommended

This allows each user to connect their own Notion workspace with a single click.

### Step 1: Create a Public Integration on Notion

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Fill in:
   - **Name**: "Notion Capture" (or your app name)
   - **Associated workspace**: Select any workspace (users will authorize their own)
   - **Type**: Select **"Public"** ⚠️ Important!
4. Click **"Submit"**

### Step 2: Configure OAuth Settings

After creating the integration:

1. Go to the **"Distribution"** tab
2. Fill in your company/developer information
3. Under **"OAuth Domain & URIs"**:
   - **Redirect URIs**: Add `http://127.0.0.1:8000/notion/auth/callback`
   - For production, also add your production callback URL (must be HTTPS)
4. **Website**: Add your app's website URL
5. Click **"Submit"** to save

### Step 3: Get Your OAuth Credentials

1. Go to the **"Secrets"** tab
2. Copy:
   - **OAuth client ID** (looks like: `abc123-def456-...`)
   - **OAuth client secret** (click "Show" then copy)

### Step 4: Add to Environment

Add these to your `.env` file in the `backend/` directory:

```bash
NOTION_CLIENT_ID=your_oauth_client_id_here
NOTION_CLIENT_SECRET=your_oauth_client_secret_here
NOTION_REDIRECT_URI=http://127.0.0.1:8000/notion/auth/callback
```

### Step 5: Restart the Backend

```bash
# Stop the server (Ctrl+C) and restart
uvicorn app.main:app --reload
```

### How OAuth Works

1. User clicks **"Connect to Notion"** in the app
2. Browser opens Notion's authorization page
3. User selects a workspace and grants access
4. Notion redirects back to your app with an access token
5. The app stores the token and can now access that user's Notion

### What Users See

When connecting:
1. Notion asks which workspace to connect
2. Notion shows which pages/databases the app can access
3. User clicks "Select pages" and grants access
4. User is redirected back to the app

---

## Option 2: Internal Integration (API Key) - For Personal Use

This is simpler but requires users to manually copy their API key.

### Step 1: Create an Internal Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Fill in:
   - **Name**: "Notion Capture" (or any name)
   - **Associated workspace**: Select your workspace
   - **Type**: Keep as **"Internal"** (default)
4. Click **"Submit"**

### Step 2: Copy the API Token

1. After creating, you'll see the **"Internal Integration Secret"**
2. Click **"Show"** then **"Copy"**
3. It looks like: `secret_abc123xyz...`

### Step 3: Share Pages with the Integration

**Important:** Your integration can only access pages you explicitly share with it.

1. Open Notion and go to the page containing your databases
2. Click the **"..."** menu (top right)
3. Click **"Connections"** (or "Add connections")
4. Search for and select your integration ("Notion Capture")
5. Click **"Confirm"**

Repeat for any pages/databases you want the app to access.

### Step 4: Enter API Key in the App

1. Open Notion Capture
2. Go to **Configure** tab
3. Paste your API key in the Notion section
4. Click **Connect**

---

## How the Integration Works

### Database Discovery
When connected, the app searches for all databases you've shared with the integration.

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

---

## Troubleshooting

### "Notion OAuth not configured"
Add `NOTION_CLIENT_ID` and `NOTION_CLIENT_SECRET` to your `.env` file and restart the backend.

### "Notion not connected"
- For OAuth: Click "Connect to Notion" and complete the authorization
- For API Key: Enter a valid API key starting with `secret_`

### "No databases found"
For Internal Integrations: Share pages with your integration:
1. Go to the Notion page with your databases
2. Click "..." → "Connections" → Add your integration

For Public Integrations: Users must select pages to share during the OAuth flow.

### "Failed to create page"
Check that:
1. The database has been shared with the integration
2. The database has a title/name property
3. Your integration has "Insert content" capability

### "Token expired or invalid"
Reconnect to Notion to get a fresh access token.

---

## Capabilities Required

Your integration needs these capabilities:
- ✅ Read content
- ✅ Update content  
- ✅ Insert content

For Public Integrations, these are configured in the integration settings.
For Internal Integrations, verify at [notion.so/my-integrations](https://www.notion.so/my-integrations) → Select your integration → "Capabilities"

---

## Production Deployment

For production deployment with OAuth:

1. Use HTTPS for your redirect URI (Notion requires HTTPS for production)
2. Update `NOTION_REDIRECT_URI` in your `.env` to your production URL
3. Add the production redirect URI in your Notion integration settings
4. Submit your integration for review if you want it listed publicly

Example production `.env`:
```bash
NOTION_CLIENT_ID=your_oauth_client_id
NOTION_CLIENT_SECRET=your_oauth_client_secret
NOTION_REDIRECT_URI=https://yourapp.com/notion/auth/callback
```
