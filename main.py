from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
import json
import random
import asyncio
from rapidfuzz import fuzz
import yt_dlp

LEADERBOARD_FILE = "leaderboard.json"
QUESTIONS_FILE = "songs.json"

NUMBER_OF_QUESTIONS_PER_ROUND = 10
DELAY_BETWEEN_ROUNDS = 30
ANSWER_TIMEOUT = 0
PREVIEW_DURATION = 12
FUZZ_THRESHOLD = 85

def load_questions():
    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"Loaded {len(data)} music questions.")
            return data
    except FileNotFoundError:
        print(f"❌ Error: {QUESTIONS_FILE} not found!")
        return []
    except json.JSONDecodeError:
        print(f"❌ Error: {QUESTIONS_FILE} is not valid JSON!")
        return []

questions = load_questions()

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except:
            return {}
    return {}

def save_leaderboard(data):
    with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

leaderboard_data = load_leaderboard()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

current_question = None
current_answer = None
players = {}
game_active = False
current_round_questions = []
answered_correctly = []
answered_this_round = set()
accepting_answers = False

async def send_embed(channel, message, title=None, color=0x3498db):
    embed = discord.Embed(description=message, color=color)
    if title:
        embed.title = title
    await channel.send(embed=embed)

def get_category_from_question(question_text):
    return question_text.split("\n")[0].strip()

def get_round_categories(questions_list):
    return [get_category_from_question(q["question"]) for q in questions_list]

def get_audio_info(yt_url):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(yt_url, download=False)
        audio_url = info.get("url")
        duration = info.get("duration")
        return audio_url, duration

async def validate_and_prepare_questions(sampled_questions):
    prepared_questions = []
    pool = [q for q in questions if q not in sampled_questions]
    used_questions = set()

    for q in sampled_questions:
        playable = False
        attempt_q = q
        attempts = 0

        while not playable and attempts < 5:
            try:
                audio_url, duration = get_audio_info(attempt_q["url"])
                if audio_url and duration and duration > PREVIEW_DURATION:
                    attempt_q = dict(attempt_q)
                    attempt_q["audio_url"] = audio_url
                    attempt_q["duration"] = duration
                    prepared_questions.append(attempt_q)
                    playable = True
                    used_questions.add(attempt_q["question"])
                else:
                    raise Exception("No valid audio URL or too short duration")
            except Exception:
                attempts += 1
                replacements = [q for q in pool if q["question"] not in used_questions]
                if replacements:
                    attempt_q = replacements.pop(random.randint(0, len(replacements)-1))
                    pool.remove(attempt_q)
                else:
                    attempt_q = q
                    attempt_q["audio_url"] = None
                    attempt_q["duration"] = 0
                    prepared_questions.append(attempt_q)
                    playable = True
                    used_questions.add(attempt_q["question"])

    return prepared_questions

async def play_preview(vc, audio_url, offset, duration=PREVIEW_DURATION):
    fade_in_duration = 2
    fade_out_duration = 3
    fade_out_start = duration - fade_out_duration

    ffmpeg_options = (
        f"-vn -af afade=t=in:ss=0:d={fade_in_duration},afade=t=out:st={fade_out_start}:d={fade_out_duration}"
    )
    source = discord.FFmpegPCMAudio(
        audio_url,
        before_options=f"-ss {offset} -t {duration}",
        options=ffmpeg_options,
    )
    vc.play(source)
    while vc.is_playing():
        await asyncio.sleep(0.5)

async def start_new_round(guild):
    global game_active, players, answered_correctly, answered_this_round, current_round_questions, accepting_answers

    if game_active:
        return

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

    game_active = True
    players = {m.display_name: 0 for m in guild.members if not m.bot}
    answered_correctly = []
    answered_this_round = set()
    accepting_answers = False

    sampled = random.sample(questions, min(NUMBER_OF_QUESTIONS_PER_ROUND, len(questions)))
    current_round_questions = await validate_and_prepare_questions(sampled)

    categories = get_round_categories(current_round_questions)
    await send_embed(text_channel, "\n".join(categories), title="🎯 Next Round Preview")
    await send_embed(text_channel, f"New round about to begin... ⏱️ {len(current_round_questions)} new questions!\n\n **Make sure you atre connected to the voice channel #music-questions to hear the songs** 🎵", title="🧐 Quiz Starting!")
    await asyncio.sleep(7)

    vc = None
    try:
        existing_vc = discord.utils.get(bot.voice_clients, guild=guild)
        if existing_vc and existing_vc.channel.id == voice_channel.id:
            vc = existing_vc
        else:
            vc = await voice_channel.connect()
    except Exception as e:
        await send_embed(text_channel, f"⚠️ Could not connect to voice channel: {e}", title="Connection Error")
        vc = None

    for index, q in enumerate(current_round_questions, start=1):
        await ask_single_question(text_channel, index, q, vc)
        await asyncio.sleep(7)

    await end_round(text_channel, guild, vc)

async def ask_single_question(channel, index, q, vc):
    global current_question, current_answer, answered_correctly, answered_this_round, accepting_answers, players

    current_question = q["question"]
    current_answer = q["answer"].lower().strip()
    answered_correctly = []
    answered_this_round = set()
    accepting_answers = True

    await send_embed(channel, f"**Question {index}:**\n{current_question}")

    if vc and q.get("audio_url"):
        try:
            audio_url = q["audio_url"]
            duration = q["duration"]
            offset = int(duration * 0.2) if duration else 0
            max_offset = duration - PREVIEW_DURATION if duration else 0
            if offset > max_offset:
                offset = max(0, max_offset)
            await play_preview(vc, audio_url, offset=offset, duration=PREVIEW_DURATION)
        except Exception:
            # Ignore playback errors silently
            pass

    try:
        await asyncio.sleep(ANSWER_TIMEOUT)
    finally:
        accepting_answers = False

    if not answered_correctly:
        await send_embed(channel, f"No one got it! Correct answer: **{current_answer.title()}**", title="⏰ Time's Up!")
    else:
        results = "\n".join(f"{i+1}. {p} (+{pts} pts)" for i, (p, pts) in enumerate(answered_correctly))
        await send_embed(channel, f"Correct answer: **{current_answer.title()}**\n\n{results}", title="✅ Results")

        sorted_round_scores = sorted(players.items(), key=lambda x: x[1], reverse=True)
        round_scores_lines = [f"{i+1}. {name} (+{score})" for i, (name, score) in enumerate(sorted_round_scores)]
        await send_embed(channel, "\n".join(round_scores_lines), title="📊 Round Scores")

async def end_round(channel, guild, vc):
    global game_active, leaderboard_data, players

    game_active = False

    max_score = max(players.values()) if players else 0
    winners = [p for p, s in players.items() if s == max_score] if max_score > 0 else []

    if winners:
        await send_embed(channel, f"Winner: {', '.join(winners)} ({max_score} points)", title="🏁 Round Over!")
    else:
        await send_embed(channel, "No winners this round.", title="🏁 Round Over!")

    for player, score in players.items():
        leaderboard_data[player] = leaderboard_data.get(player, 0) + score
    save_leaderboard(leaderboard_data)

    await show_leaderboard(channel)

    await send_embed(channel, f"Next round starts in {DELAY_BETWEEN_ROUNDS} seconds…", title="⏳ Waiting")
    try:
        if vc and not vc.is_playing():
            await vc.disconnect()
    except Exception:
        pass

    await asyncio.sleep(DELAY_BETWEEN_ROUNDS)
    await start_new_round(guild)

async def show_leaderboard(channel, round_over=False):
    if not leaderboard_data:
        await send_embed(channel, "Nobody has scored yet.", title="Leaderboard")
        return
    sorted_scores = sorted(leaderboard_data.items(), key=lambda x: x[1], reverse=True)
    lines = [f"**{i+1}. {name} ({score} points)**" for i, (name, score) in enumerate(sorted_scores)]
    await send_embed(channel, "\n".join(lines), title="🏆 Leaderboard 🏆")

@bot.command()
async def leaderboard(ctx):
    await show_leaderboard(ctx.channel)

@bot.command()
async def endquiz(ctx):
    global game_active
    game_active = False
    await ctx.send("🛑 Quiz ended manually.")

@bot.event
async def on_message(message):
    global answered_correctly, accepting_answers, players, answered_this_round

    await bot.process_commands(message)

    if (
        message.author.bot
        or not game_active
        or not accepting_answers
    ):
        return

    try:
        text_channel_id = int(os.getenv("MUSIC_TEXT_CHANNEL") or 0)
    except:
        text_channel_id = 0

    if message.channel.id != text_channel_id:
        return

    user_answer = message.content.strip().lower()
    match_score = fuzz.ratio(user_answer, current_answer) if current_answer else 0

    if match_score >= FUZZ_THRESHOLD and message.author.id not in answered_this_round and len(answered_correctly) < 3:
        answered_this_round.add(message.author.id)
        player = message.author.display_name
        points_awarded = [15, 10, 5][len(answered_correctly)]

        if player not in players:
            players[player] = 0

        players[player] += points_awarded
        answered_correctly.append((player, points_awarded))

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}!")
    guild = bot.guilds[0] if bot.guilds else None
    if not guild:
        print("❌ Bot is not in any guilds. Add it to your server and restart.")
        return
    await asyncio.sleep(3)
    await start_new_round(guild)

if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ Error: DISCORD_TOKEN environment variable not found!")
    else:
        bot.run(token)
