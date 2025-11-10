import os
import base64
import aiohttp
import asyncio

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
TOKEN_URL = "https://accounts.spotify.com/api/token"

class SpotifyAPI:
    def __init__(self):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.access_token = None
        self.token_expires = 0
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    async def get_token(self):
        auth_str = f"{self.client_id}:{self.client_secret}"
        b64_auth_str = base64.b64encode(auth_str.encode()).decode()
        headers = {
            "Authorization": f"Basic {b64_auth_str}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = "grant_type=client_credentials"

        async with self.session.post(TOKEN_URL, headers=headers, data=data) as resp:
            resp.raise_for_status()
            token_data = await resp.json()
            self.access_token = token_data["access_token"]
            # Optionally handle expires_in for refreshing token if needed

    async def _get_headers(self):
        if not self.access_token:
            await self.get_token()
        return {"Authorization": f"Bearer {self.access_token}"}

    async def get_playlist_tracks(self, playlist_id, limit=100):
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        headers = await self._get_headers()
        params = {"limit": limit}

        async with self.session.get(url, headers=headers, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("items", [])

    # You can add more methods similarly if needed
