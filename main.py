import os
import re
import time
from pathlib import Path

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
		if key and key not in os.environ:
			os.environ[key] = value


def build_spotify_client() -> spotipy.Spotify:
	load_env_file()

	client_id = os.getenv("SPOTIFY_CLIENT_ID")
	client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
	redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "https://python_automation.com")

	if not client_id or not client_secret:
		raise RuntimeError(
			"Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables first."
		)

	auth_manager = SpotifyOAuth(
		client_id=client_id,
		client_secret=client_secret,
		redirect_uri=redirect_uri,
		scope=SCOPE,
		open_browser=True,
		cache_path=".cache",
	)
	return spotipy.Spotify(auth_manager=auth_manager)


def listen_for_command(recognizer: sr.Recognizer, microphone: sr.Microphone) -> str | None:
	with microphone as source:
		print("Listening...")
		recognizer.adjust_for_ambient_noise(source, duration=0.5)
		audio = recognizer.listen(source, phrase_time_limit=6)

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


def main() -> None:
	sp = build_spotify_client()
	recognizer = sr.Recognizer()

	try:
		microphone = sr.Microphone()
	except OSError as exc:
		raise RuntimeError(f"Microphone not available: {exc}") from exc

	print("Voice-controlled Spotify ready.")
	print('Try commands like: play, pause, next, previous, volume up, play song imagine dragons, play playlist chill')

	while True:
		text = listen_for_command(recognizer, microphone)
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


if __name__ == "__main__":
	main()
