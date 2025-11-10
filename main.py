import discord
from discord.ext import commands
import asyncio
import random
import os
import json
from rapidfuzz import fuzz

TOKEN = os.getenv("DISCORD_TOKEN")
MUSIC_TEXT_CHANNEL = int(os.getenv("MUSIC_TEXT_CHANNEL"))
MUSIC_VOICE_CHANNEL = int(os.getenv("MUSIC_VOICE_CHANNEL"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

scores = {}
current_song = None
answer_found = False
fastest_answered = False

async def load_tracks_from_json(filename="songs.json"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            tracks = json.load(f)
        print(f"Loaded {len(tracks)} tracks from {filename}.")
        return tracks
    except FileNotFoundError:
        print(f"❌ JSON file {filename} not found.")
        return []
    except Exception as e:
        print(f"❌ Error loading JSON file: {e}")
        return []

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

    # Connect to voice channel, check if already connected first
    if not bot.voice_clients or not any(vc.channel.id == MUSIC_VOICE_CHANNEL for vc in bot.voice_clients):
        vc = await vc_channel.connect()
    else:
        vc = discord.utils.get(bot.voice_clients, channel=vc_channel)

    await channel.send("🎶 **Welcome to Music Trivia!** Guess the song title as fast as you can!")

    songs = await load_tracks_from_json("songs.json")
    if len(songs) < 10:
        await channel.send("⚠️ Not enough tracks in the JSON database!")
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
