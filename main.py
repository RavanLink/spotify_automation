import os
import re
import time
import webbrowser
import argparse
from pathlib import Path
from urllib.parse import urlparse

import speech_recognition as sr
import spotipy
from spotipy.oauth2 import SpotifyOAuth


SCOPE = " ".join(
	[
		"user-read-playback-state",
		"user-modify-playback-state",
		"user-read-currently-playing",
		"playlist-read-private",
		"playlist-modify-private",
		"playlist-modify-public",
	]
)


def validate_redirect_uri(redirect_uri: str) -> tuple[bool, str]:
	parsed = urlparse(redirect_uri)
	if parsed.scheme not in {"http", "https"}:
		return False, "Redirect URI must start with http:// or https://"

	host = (parsed.hostname or "").lower()
	if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1"}:
		return False, "Only localhost/127.0.0.1 are allowed for http redirect URIs"

	if not parsed.path:
		return False, "Redirect URI should include a callback path (example: /callback)"

	return True, "ok"


def load_env_file(path: str = ".env") -> None:
	env_path = Path(path)
	if not env_path.exists():
		return

	for raw_line in env_path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue

		key, value = line.split("=", 1)
		key = key.strip()
		value = value.strip().strip('"').strip("'")
		if key:
			os.environ[key] = value


def build_spotify_client() -> spotipy.Spotify:
	load_env_file()

	client_id = os.getenv("SPOTIFY_CLIENT_ID")
	client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
	redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

	if not client_id or not client_secret:
		raise RuntimeError(
			"Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables first."
		)

	if "open.spotify.com" in redirect_uri.lower():
		raise RuntimeError(
			"SPOTIFY_REDIRECT_URI cannot be open.spotify.com. Use a callback URL like http://localhost:8888/callback and set the same URI in Spotify Developer Dashboard."
		)

	is_valid_redirect, redirect_message = validate_redirect_uri(redirect_uri)
	if not is_valid_redirect:
		raise RuntimeError(f"Invalid SPOTIFY_REDIRECT_URI: {redirect_message}")

	print(f"Using redirect URI: {redirect_uri}")

	is_local_http = redirect_uri.lower().startswith("http://localhost")
	is_local_http = is_local_http or redirect_uri.lower().startswith("http://127.0.0.1")

	auth_manager = SpotifyOAuth(
		client_id=client_id,
		client_secret=client_secret,
		redirect_uri=redirect_uri,
		scope=SCOPE,
		open_browser=is_local_http,
		cache_path=".cache",
	)

	if not is_local_http and not auth_manager.validate_token(auth_manager.cache_handler.get_cached_token()):
		auth_url = auth_manager.get_authorize_url()
		print("Open this URL and approve access:")
		print(auth_url)
		print("Important: the redirect URI in this URL must exactly match your Spotify app setting, including http/https, port, path, and trailing slash.")
		try:
			webbrowser.open(auth_url)
		except Exception:
			pass

		redirect_response = input("Paste the full redirected URL here: ").strip()
		code = auth_manager.parse_response_code(redirect_response)
		if not code:
			raise RuntimeError("Could not parse authorization code from redirect URL.")
		auth_manager.get_access_token(code, check_cache=False)

	return spotipy.Spotify(auth_manager=auth_manager)


def run_doctor() -> int:
	load_env_file()
	print("Running preflight checks...")

	client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
	client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
	redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "")

	if not client_id:
		print("FAIL: SPOTIFY_CLIENT_ID is missing")
		return 1
	print("OK: SPOTIFY_CLIENT_ID found")

	if not client_secret:
		print("FAIL: SPOTIFY_CLIENT_SECRET is missing")
		return 1
	print("OK: SPOTIFY_CLIENT_SECRET found")

	if not redirect_uri:
		print("FAIL: SPOTIFY_REDIRECT_URI is missing")
		return 1

	ok_redirect, msg = validate_redirect_uri(redirect_uri)
	if not ok_redirect:
		print(f"FAIL: SPOTIFY_REDIRECT_URI invalid: {msg}")
		return 1
	print(f"OK: SPOTIFY_REDIRECT_URI format valid: {redirect_uri}")

	if redirect_uri.lower().startswith("https://localhost"):
		print("WARN: Some providers reject https://localhost as insecure. If auth fails, use a public HTTPS callback URL and manual paste flow.")

	if redirect_uri.lower().startswith("http://localhost") or redirect_uri.lower().startswith("http://127.0.0.1"):
		print("INFO: Local callback flow will auto-open browser.")
	else:
		print("INFO: Non-local callback flow will ask you to paste redirected URL.")

	try:
		mic_names = sr.Microphone.list_microphone_names()
		if mic_names:
			print(f"OK: Microphone devices detected: {len(mic_names)}")
		else:
			print("WARN: No microphone devices detected")
	except Exception as exc:
		print(f"WARN: Could not list microphones: {exc}")

	try:
		auth_manager = SpotifyOAuth(
			client_id=client_id,
			client_secret=client_secret,
			redirect_uri=redirect_uri,
			scope=SCOPE,
			open_browser=False,
			cache_path=".cache",
		)
		auth_url = auth_manager.get_authorize_url()
		print("OK: Spotify authorize URL generated")
		print(f"INFO: Authorize URL starts with: {auth_url[:60]}...")
	except Exception as exc:
		print(f"FAIL: Could not initialize Spotify OAuth: {exc}")
		return 1

	print("Preflight complete: setup looks ready.")
	return 0


def listen_for_command(recognizer: sr.Recognizer, microphone: sr.Microphone) -> str | None:
	with microphone as source:
		print("Listening...")
		recognizer.adjust_for_ambient_noise(source, duration=0.5)
		try:
			audio = recognizer.listen(source, timeout=5, phrase_time_limit=6)
		except sr.WaitTimeoutError:
			print("No speech detected.")
			return None

	try:
		text = recognizer.recognize_google(audio)
		print(f"Heard: {text}")
		return text.lower().strip()
	except sr.UnknownValueError:
		print("Could not understand the audio.")
	except sr.RequestError as exc:
		print(f"Speech recognition error: {exc}")
	return None


def parse_command(text: str) -> tuple[str, str | None]:
	normalized = text.lower().strip()

	if normalized in {"exit", "quit", "stop listening"}:
		return "exit", None
	if "pause" in normalized:
		return "pause", None
	if normalized in {"play", "resume"}:
		return "play", None
	if normalized.startswith("play ") and len(normalized) > 5:
		return "play_song", normalized[5:].strip()
	if "next" in normalized or "skip" in normalized:
		return "next", None
	if "previous" in normalized or "back" in normalized:
		return "previous", None
	if "volume up" in normalized:
		return "volume_up", None
	if "volume down" in normalized:
		return "volume_down", None

	match = re.search(r"play song (.+)", normalized)
	if match:
		return "play_song", match.group(1).strip()

	match = re.search(r"play playlist (.+)", normalized)
	if match:
		return "play_playlist", match.group(1).strip()

	match = re.search(r"search (.+)", normalized)
	if match:
		return "search", match.group(1).strip()

	return "unknown", normalized


def get_active_device_id(sp: spotipy.Spotify) -> str | None:
	devices = sp.devices().get("devices", [])
	if not devices:
		return None

	preferred_name = os.getenv("SPOTIFY_DEVICE_NAME", "").strip().lower()
	if preferred_name:
		for device in devices:
			name = str(device.get("name", "")).strip().lower()
			if name == preferred_name:
				return device["id"]

	# By default, prefer desktop app devices so commands do not jump to web player.
	computer_devices = [device for device in devices if str(device.get("type", "")).lower() == "computer"]
	if computer_devices:
		active_computers = [device for device in computer_devices if device.get("is_active")]
		if active_computers:
			return active_computers[0]["id"]
		return computer_devices[0]["id"]

	active_devices = [device for device in devices if device.get("is_active")]
	if active_devices:
		return active_devices[0]["id"]

	return devices[0]["id"]


def ensure_playback_device(sp: spotipy.Spotify) -> str:
	device_id = get_active_device_id(sp)
	if device_id:
		return device_id

	raise RuntimeError(
		"No active Spotify device found. Open Spotify on a device first, then try again."
	)


def search_track_uri(sp: spotipy.Spotify, query: str) -> str | None:
	result = sp.search(q=query, type="track", limit=1)
	tracks = result.get("tracks", {}).get("items", [])
	if not tracks:
		return None
	return tracks[0]["uri"]


def search_playlist_uri(sp: spotipy.Spotify, query: str) -> str | None:
	result = sp.search(q=query, type="playlist", limit=1)
	playlists = result.get("playlists", {}).get("items", [])
	if not playlists:
		return None
	return playlists[0]["uri"]


def handle_command(sp: spotipy.Spotify, command: str, argument: str | None) -> bool:
	if command == "exit":
		return False

	device_id = ensure_playback_device(sp)

	if command == "play":
		sp.start_playback(device_id=device_id)
		print("Playback resumed.")
	elif command == "pause":
		sp.pause_playback(device_id=device_id)
		print("Playback paused.")
	elif command == "next":
		sp.next_track(device_id=device_id)
		print("Skipped to next track.")
	elif command == "previous":
		sp.previous_track(device_id=device_id)
		print("Went to previous track.")
	elif command == "volume_up":
		current = sp.current_playback()
		volume = (current.get("device", {}).get("volume_percent", 50) if current else 50) + 10
		sp.volume(min(volume, 100), device_id=device_id)
		print(f"Volume set to {min(volume, 100)}%.")
	elif command == "volume_down":
		current = sp.current_playback()
		volume = (current.get("device", {}).get("volume_percent", 50) if current else 50) - 10
		sp.volume(max(volume, 0), device_id=device_id)
		print(f"Volume set to {max(volume, 0)}%.")
	elif command == "play_song" and argument:
		uri = search_track_uri(sp, argument)
		if not uri:
			print(f"No track found for: {argument}")
			return True
		sp.start_playback(device_id=device_id, uris=[uri])
		print(f"Playing song: {argument}")
	elif command == "play_playlist" and argument:
		uri = search_playlist_uri(sp, argument)
		if not uri:
			print(f"No playlist found for: {argument}")
			return True
		sp.start_playback(device_id=device_id, context_uri=uri)
		print(f"Playing playlist: {argument}")
	elif command == "search" and argument:
		uri = search_track_uri(sp, argument)
		if uri:
			print(f"Found track URI: {uri}")
		else:
			print(f"No track found for: {argument}")
	else:
		print(f"Unknown command: {argument or command}")

	return True


def main() -> int:
	parser = argparse.ArgumentParser(description="Voice-controlled Spotify automation")
	parser.add_argument("--doctor", action="store_true", help="Run preflight checks and exit")
	args = parser.parse_args()

	if args.doctor:
		return run_doctor()

	sp = build_spotify_client()
	recognizer = sr.Recognizer()
	recognizer.operation_timeout = 8

	try:
		microphone = sr.Microphone()
	except OSError as exc:
		raise RuntimeError(f"Microphone not available: {exc}") from exc

	print("Voice-controlled Spotify ready.")
	print('Try commands like: play, pause, next, previous, volume up, play song imagine dragons, play playlist chill')

	while True:
		try:
			text = listen_for_command(recognizer, microphone)
		except KeyboardInterrupt:
			print("\nStopped by user.")
			break

		if not text:
			time.sleep(0.5)
			continue

		command, argument = parse_command(text)
		try:
			keep_running = handle_command(sp, command, argument)
		except Exception as exc:
			print(f"Command failed: {exc}")
			keep_running = True

		if not keep_running:
			break

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
