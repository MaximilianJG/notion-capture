# Google Calendar Integration Setup

To enable Google Calendar integration, you need to set up OAuth credentials.

## Steps:

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/

2. **Create a New Project** (or select existing)
   - Click "Select a project" → "New Project"
   - Give it a name (e.g., "Screenshot Calendar")

3. **Enable Google Calendar API**
   - Go to "APIs & Services" → "Library"
   - Search for "Google Calendar API"
   - Click "Enable"

4. **Configure OAuth Consent Screen** (IMPORTANT - Do this FIRST!)
   - Go to "APIs & Services" → "OAuth consent screen"
   - User Type: **External** (for testing) or Internal (if you have Google Workspace)
   - Click "Create"
   - Fill in the required fields:
     - **App name**: Screenshot Calendar (or your choice)
     - **User support email**: Select your email
     - **Developer contact information**: Enter your email
   - Click "Save and Continue"
   
   - **Scopes** (Step 2):
     - Click "Add or Remove Scopes"
     - Search for and select: `https://www.googleapis.com/auth/calendar`
     - Click "Update" then "Save and Continue"
   
   - **Test users** (Step 3) - **CRITICAL STEP!**:
     - Click "Add Users"
     - **Add your Google account email address** (the one you'll use to connect)
     - Click "Add"
     - Click "Save and Continue"
   
   - Review and click "Back to Dashboard"

5. **Create OAuth Client ID**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   
   - Application type: **"Web application"**
   - Name: "Screenshot Calendar Client"
   - **Authorized redirect URIs**: 
     - Click "Add URI"
     - Add: `http://127.0.0.1:8000/google/auth/callback`
     - Click "Create"
   - **Download the JSON file** (click the download icon)

6. **Save Credentials**
   - Rename the downloaded JSON file to `client_secret.json`
   - Place it in the `backend/` directory (same folder as `main.py`)

7. **Update Environment Variable (Optional)**
   - If you want to use a different filename or path, set:
     ```bash
     export GOOGLE_CLIENT_SECRETS_FILE="path/to/your/client_secret.json"
     ```

## Troubleshooting: "Error 403: access_denied"

If you see this error, it means **you haven't added yourself as a test user**:

1. Go to Google Cloud Console → "APIs & Services" → "OAuth consent screen"
2. Scroll down to **"Test users"** section
3. Click **"Add Users"**
4. Enter **your Google account email** (the exact email you're trying to connect with)
5. Click **"Add"**
6. Click **"Save"**
7. Try connecting again in the app

**Important**: The email you add as a test user must match the Google account you're using to authenticate!

## Testing

1. Make sure you've added yourself as a test user (see troubleshooting above)
2. Start your FastAPI server
3. Click "Connect Google" in the macOS app
4. Complete the OAuth flow in your browser
5. You should see "✓ Google Connected" in the app

## Notes

- The OAuth token is stored in `token.pickle` in the backend directory
- You can revoke access at: https://myaccount.google.com/permissions
- For production, use proper OAuth redirect URIs matching your deployment

