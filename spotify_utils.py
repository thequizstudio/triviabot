import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
TOKEN_URL = "https://accounts.spotify.com/api/token"

class SpotifyAPI:
    def __init__(self):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.access_token = None
        self.token_type = None
        self.expires_in = None
        self.get_token()

    def get_token(self):
        auth_str = f"{self.client_id}:{self.client_secret}"
        b64_auth_str = base64.b64encode(auth_str.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_auth_str}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}

        response = requests.post(TOKEN_URL, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()

        self.access_token = token_data["access_token"]
        self.token_type = token_data["token_type"]
        self.expires_in = token_data["expires_in"]

    def _get_headers(self):
        if not self.access_token:
            self.get_token()
        return {"Authorization": f"Bearer {self.access_token}"}

    def search_tracks(self, query, limit=10):
        url = "https://api.spotify.com/v1/search"
        headers = self._get_headers()
        params = {
            "q": query,
            "type": "track",
            "limit": limit
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("tracks", {}).get("items", [])

    def get_playlist_tracks(self, playlist_id, limit=100):
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        headers = self._get_headers()
        params = {
            "limit": limit
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("items", [])

# Example usage:
# spotify = SpotifyAPI()
# tracks = spotify.search_tracks("Bohemian Rhapsody")
# for track in tracks:
#     print(track["name"], track["preview_url"])
