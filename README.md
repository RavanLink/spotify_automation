# spotify_automation

## Setup

This project reads Spotify credentials from a local `.env` file (or system environment variables).

Create a local `.env` file in the project root with:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

Important: `SPOTIFY_REDIRECT_URI` must exactly match the Redirect URI configured in Spotify Developer Dashboard.

If you prefer not to use `.env`, you can still use environment variables.

Example PowerShell session:

```powershell
$env:SPOTIFY_CLIENT_ID="your_client_id_here"
$env:SPOTIFY_CLIENT_SECRET="your_client_secret_here"
$env:SPOTIFY_REDIRECT_URI="http://localhost:8888/callback"
```

Then run:

```powershell
.\.venv\Scripts\python.exe main.py
```