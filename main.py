import discord
from discord.ext import commands
import asyncio
import random
import os
from rapidfuzz import fuzz
from spotify_utils import SpotifyAPI

# Removed load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
MUSIC_TEXT_CHANNEL = int(os.getenv("MUSIC_TEXT_CHANNEL"))
MUSIC_VOICE_CHANNEL = int(os.getenv("MUSIC_VOICE_CHANNEL"))
SPOTIFY_PLAYLIST_ID = os.getenv("SPOTIFY_PLAYLIST_ID")  # Just the playlist ID, not full URL

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

scores = {}
current_song = None
answer_found = False
fastest_answered = False

spotify = SpotifyAPI()  # Instantiate Spotify API helper


async def load_spotify_songs():
    print(f"Fetching tracks from Spotify playlist {SPOTIFY_PLAYLIST_ID}...")
    items = spotify.get_playlist_tracks(SPOTIFY_PLAYLIST_ID, limit=100)
    tracks = []
    for item in items:
        track = item.get("track")
        if not track:
            continue
        preview_url = track.get("preview_url")
        if not preview_url:
            continue  # skip tracks with no preview clip

        tracks.append({
            "artist": track["artists"][0]["name"],
            "title": track["name"],
            "preview_url": preview_url,
            "answer": track["name"]
        })

    print(f"Loaded {len(tracks)} previewable tracks from Spotify.")
    return tracks


async def start_music_round():
    try:
        channel = await bot.fetch_channel(MUSIC_TEXT_CHANNEL)
    except discord.NotFound:
        print("❌ Text channel not found via fetch_channel.")
        return
    except discord.Forbidden:
        print("❌ No permission to fetch the text channel.")
        return
    except Exception as e:
        print(f"❌ Unexpected error fetching text channel: {e}")
        return

    vc_channel = bot.get_channel(MUSIC_VOICE_CHANNEL)
    if not vc_channel:
        await channel.send("❌ Voice channel not found.")
        return

    vc = await vc_channel.connect()
    await channel.send("🎶 **Welcome to Music Trivia!** Guess the song title as fast as you can!")

    songs = await load_spotify_songs()
    if len(songs) < 10:
        await channel.send("⚠️ Not enough tracks with preview URLs in the playlist!")
        await vc.disconnect()
        return

    random.shuffle(songs)

    global current_song, answer_found, fastest_answered

    for i, song in enumerate(songs[:10], 1):
        current_song, answer_found, fastest_answered = song, False, False

        await channel.send(f"▶️ **Song {i}/10** — listen carefully!")
        vc.play(
            discord.FFmpegPCMAudio(
                song["preview_url"],
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn"
            )
        )
        await asyncio.sleep(10)  # play 10-second preview
        vc.stop()

        if not answer_found:
            await channel.send(f"⏰ Time's up! The answer was **{song['title']}** by *{song['artist']}*.")
        await asyncio.sleep(6)

    await vc.disconnect()
    await show_leaderboard(channel)
    await channel.send("🎵 Round complete! Type `!music` to start another game.")


@bot.event
async def on_ready():
    print(f"{bot.user} is live as the Music Trivia Bot 🎵")
    # Auto-start on bot ready:
    await start_music_round()


@bot.event
async def on_message(message):
    global answer_found, fastest_answered

    if message.author.bot or message.channel.id != MUSIC_TEXT_CHANNEL:
        return

    if current_song and not answer_found:
        guess = message.content.lower()
        correct = current_song["answer"].lower()
        ratio = fuzz.partial_ratio(guess, correct)
        if ratio >= 80:
            answer_found = True
            user = message.author

            if not fastest_answered:
                fastest_answered = True
                scores[user] = scores.get(user, 0) + 15  # 10 pts + 5 bonus
                await message.channel.send(
                    f"⚡ {user.mention} got it first! **{current_song['title']}** (+15 pts)"
                )
            else:
                scores[user] = scores.get(user, 0) + 10
                await message.channel.send(
                    f"✅ {user.mention} got it! **{current_song['title']}** (+10 pts)"
                )

    await bot.process_commands(message)


async def show_leaderboard(channel):
    if not scores:
        await channel.send("No correct answers this round.")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    leaderboard = "\n".join(
        [f"**{i+1}. {user.display_name}** — {points} pts" for i, (user, points) in enumerate(sorted_scores)]
    )
    await channel.send(f"🏆 **Final Leaderboard:**\n{leaderboard}")


@bot.command(name="music")
async def manual_start(ctx):
    await ctx.send("🎧 Starting a new music trivia round!")
    await start_music_round()


bot.run(TOKEN)
