import discord
import asyncio
import yt_dlp
import json
import random
import os
from discord.ext import commands

# ---- BOT CONFIG ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- LOAD QUESTIONS ----
def load_questions():
    try:
        with open("music_questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Error: music_questions.json not found!")
        return []
    except json.JSONDecodeError:
        print("❌ Error: JSON file is invalid!")
        return []

questions = load_questions()

# ---- YOUTUBE AUDIO FETCH ----
def get_audio_url(yt_url):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "skip_download": True,
        "no_warnings": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(yt_url, download=False)
        return info["url"]

# ---- AUDIO PLAYBACK ----
async def play_preview(vc, audio_url, duration=7):
    """Play a short audio preview."""
    source = discord.FFmpegPCMAudio(
        audio_url,
        before_options=f"-ss 0 -t {duration}",
        options="-vn"
    )
    vc.play(source)
    while vc.is_playing():
        await asyncio.sleep(0.5)

# ---- QUIZ LOGIC ----
async def start_quiz(bot):
    """Automatically start a quiz in the configured text and voice channels."""
    text_channel_id = os.getenv("MUSIC_TEXT_CHANNEL")
    voice_channel_id = os.getenv("MUSIC_VOICE_CHANNEL")

    if not text_channel_id or not voice_channel_id:
        print("❌ Missing MUSIC_TEXT_CHANNEL or MUSIC_VOICE_CHANNEL environment variable.")
        return

    try:
        text_channel = bot.get_channel(int(text_channel_id))
        voice_channel = bot.get_channel(int(voice_channel_id))
    except Exception as e:
        print(f"❌ Could not access configured channels: {e}")
        return

    if not text_channel or not voice_channel:
        print("❌ Invalid text or voice channel IDs. Check your Railway variables.")
        return

    # Connect to the voice channel
    vc = await voice_channel.connect()

    score = {}
    random.shuffle(questions)
    total_questions = min(10, len(questions))

    await text_channel.send(f"🎵 Starting a {total_questions}-question music quiz!")

    for i, q in enumerate(questions[:total_questions], start=1):
        await text_channel.send(f"**Question {i}/{total_questions}**\n{q['question']}")

        try:
            audio_url = get_audio_url(q["url"])
            await play_preview(vc, audio_url)
        except Exception as e:
            await text_channel.send(f"⚠️ Error playing track: {e}")
            continue

        def check(m):
            return m.channel == text_channel and not m.author.bot

        try:
            msg = await bot.wait_for("message", timeout=10.0, check=check)
        except asyncio.TimeoutError:
            await text_channel.send(f"⏰ Time’s up! The answer was **{q['answer']}**")
            await asyncio.sleep(2)
            continue

        if msg.content.lower().strip() == q["answer"].lower().strip():
            score[msg.author] = score.get(msg.author, 0) + 10
            await text_channel.send(f"✅ Correct, {msg.author.display_name}! (+10 points)")
        else:
            await text_channel.send(f"❌ Nope — the correct answer was **{q['answer']}**")

        await asyncio.sleep(3)

    if score:
        leaderboard = "\n".join(
            [f"{user.display_name}: {points}" for user, points in sorted(score.items(), key=lambda x: x[1], reverse=True)]
        )
        await text_channel.send(f"🏁 **Final Leaderboard:**\n{leaderboard}")
    else:
        await text_channel.send("😅 No one scored this round!")

    await vc.disconnect()

# ---- ON READY ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("🎶 Music trivia bot is ready.")

    # Automatically start the quiz once the bot is ready
    await asyncio.sleep(3)
    await start_quiz(bot)

# ---- START BOT (from Railway variable) ----
token = os.getenv("DISCORD_TOKEN")

if not token:
    print("❌ Error: DISCORD_TOKEN environment variable not found!")
else:
    bot.run(token)
