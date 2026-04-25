# spotify_automation

## Setup

This project reads Spotify credentials from a local `.env` file (or system environment variables).

Create a local `.env` file in the project root with:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
# Optional: exact Spotify device name to control (recommended for desktop app)
# SPOTIFY_DEVICE_NAME=DESKTOP-XXXXXX
```

Important: `SPOTIFY_REDIRECT_URI` must exactly match the Redirect URI configured in Spotify Developer Dashboard.

The app now prefers desktop (`Computer`) Spotify devices by default, so commands are less likely to switch to Web Player.
If you want exact targeting, set `SPOTIFY_DEVICE_NAME` to your Spotify device name.

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