import discord
import asyncio
import yt_dlp
import json
import random
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

# ---- QUIZ COMMAND ----
@bot.command()
async def quiz(ctx):
    """Start a 10-question music quiz."""
    if not ctx.author.voice:
        await ctx.send("🎧 You need to join a voice channel first!")
        return

    channel = ctx.author.voice.channel
    vc = await channel.connect()

    score = {}
    random.shuffle(questions)
    total_questions = min(10, len(questions))

    await ctx.send(f"🎵 Starting a {total_questions}-question music quiz!")

    for i, q in enumerate(questions[:total_questions], start=1):
        await ctx.send(f"**Question {i}/{total_questions}**\n{q['question']}")

        try:
            audio_url = get_audio_url(q["url"])
            await play_preview(vc, audio_url)
        except Exception as e:
            await ctx.send(f"⚠️ Error playing track: {e}")
            continue

        def check(m):
            return m.channel == ctx.channel and not m.author.bot

        try:
            msg = await bot.wait_for("message", timeout=10.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Time’s up! The answer was **{q['answer']}**")
            await asyncio.sleep(2)
            continue

        if msg.content.lower().strip() == q["answer"].lower().strip():
            score[msg.author] = score.get(msg.author, 0) + 10
            await ctx.send(f"✅ Correct, {msg.author.display_name}! (+10 points)")
        else:
            await ctx.send(f"❌ Nope — the correct answer was **{q['answer']}**")

        await asyncio.sleep(3)

    if score:
        leaderboard = "\n".join(
            [f"{user.display_name}: {points}" for user, points in sorted(score.items(), key=lambda x: x[1], reverse=True)]
        )
        await ctx.send(f"🏁 **Final Leaderboard:**\n{leaderboard}")
    else:
        await ctx.send("😅 No one scored this round!")

    await vc.disconnect()

# ---- ON READY ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("🎶 Music trivia bot is ready.")

# ---- START BOT ----
bot.run("YOUR_DISCORD_BOT_TOKEN")
