print("[DEBUG] Bot script started...")
import sys
import subprocess
import os

# --- AUTOMATIC REQUIREMENTS INSTALLATION ---
def install_requirements():
    print("[DEBUG] Checking dependencies...", flush=True)
    try:
        print("[DEBUG] Checking discord...", flush=True)
        import discord
        print("[DEBUG] Checking dotenv...", flush=True)
        import dotenv
        print("[DEBUG] Checking aiohttp...", flush=True)
        import aiohttp
        print("[DEBUG] Checking google.genai...", flush=True)
        import google.genai
        print("[DEBUG] All dependencies already installed.", flush=True)
        return
    except ImportError as e:
        print(f"[DEBUG] Missing dependency: {e}", flush=True)
    except Exception as e:
        print(f"[DEBUG] Unexpected error during import check: {e}", flush=True)

    req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if os.path.exists(req_file):
        print("\n[!] IMPORTANT: Some dependencies are missing. Installing them now...", flush=True)
        print("[!] This is only done once. Please wait a moment...\n", flush=True)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            print("\n[+] Dependencies installed successfully!", flush=True)
            import importlib
            importlib.invalidate_caches()
        except Exception as e:
            print(f"\n[X] CRITICAL ERROR: Auto-installation failed: {e}", flush=True)
            print("[X] Please run 'pip install -r requirements.txt' manually in your terminal.", flush=True)
            sys.exit(1)
    else:
        print("\n[X] CRITICAL ERROR: requirements.txt not found! 🥀", flush=True)
        sys.exit(1)

install_requirements()

import discord
from discord.ext import commands
import io
import re
import time
import asyncio
import json
import aiohttp
import random
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- GLOBALS ---
start_time = time.time()
last_response_time = 0
last_channel_response_times = {}
message_context_limit = 10
COMMAND_PREFIX = "!"

# For this to work you need to have the Vertex AI .json credentials file in this folder under the name "vertex-credentials.json"
# Here is a tutorial on how to get it: https://docs.decisionrules.io/doc/ai-assistant/assistant-setup/google-vertex-credentials-json

load_dotenv()
# Required in .env:
#   GEMINI_API_KEY=your_api_key_here  (optional, only needed for song generation via Lyria)
#   DISCORD_TOKEN=your_discord_token_here

# --- FILE PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
USER_MEMORIES_FILE = os.path.join(BASE_DIR, "user_memories.json")
GLOBAL_MEMORY_FILE = os.path.join(BASE_DIR, "global_memory.txt")
PERSONALITIES_FILE = os.path.join(BASE_DIR, "user_personalities.json")
INSTRUCTIONS_FILE = os.path.join(BASE_DIR, "instructions.txt")
REFRESH_FILE = os.path.join(BASE_DIR, "refresh_channel.txt")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "vertex-credentials.json")
# config.json structure:
# {
#   "ALLOWED_CHANNELS": [],             // empty = respond everywhere
#   "COOLDOWN_SECONDS": 5,              // global cooldown
#   "CHANNEL_COOLDOWNS": {},            // {"channel_id": seconds} per-channel overrides
#   "BANNED_USERS": [],
#   "ALLOWED_IMAGE_USERS": [],
#   "ALLOWED_VIDEO_USERS": [],
#   "ALLOWED_SONG_USERS": [],
#   "ALLOWED_PERSONALITY_USERS": [],    // who can set a custom AI personality (via !personality in DMs)
#   "ACTIVE_MODEL": "gemini-2.5-flash",
#   "ACTIVE_OLLAMA_MODEL": "llama3.2",
#   "AI_BACKEND": "gemini",
#   "FEATURES": {"IMAGE_ENABLED": true, "VIDEO_ENABLED": true, "SONG_ENABLED": true}
# }

def load_config():
    default_config = {
        "ALLOWED_CHANNELS": [],
        "COOLDOWN_SECONDS": 5,
        "CHANNEL_COOLDOWNS": {},
        "BANNED_USERS": [],
        "ALLOWED_IMAGE_USERS": [],
        "ALLOWED_VIDEO_USERS": [],
        "ALLOWED_SONG_USERS": [],
        "ALLOWED_PERSONALITY_USERS": [],
        "ACTIVE_MODEL": "gemini-2.5-flash",
        "ACTIVE_OLLAMA_MODEL": "llama3.2",
        "AI_BACKEND": "gemini",
        "FEATURES": {
            "IMAGE_ENABLED": True,
            "VIDEO_ENABLED": True,
            "SONG_ENABLED": True
        }
    }
    if not os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            print(f"[+] Created default configuration: {CONFIG_FILE}")
        except Exception as e:
            print(f"[X] Failed to create config file: {e}")
        return default_config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Error reading {CONFIG_FILE}: {e}. Using default config.")
        return default_config

config_data = load_config()

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")

# --- CONFIG MIGRATIONS ---
if "ALLOWED_PAINT_USERS" in config_data:
    config_data["ALLOWED_IMAGE_USERS"] = config_data.pop("ALLOWED_PAINT_USERS")
    save_config()
for key, default in [
    ("FEATURES", {"IMAGE_ENABLED": True, "VIDEO_ENABLED": True, "SONG_ENABLED": True}),
    ("AI_BACKEND", "gemini"),
    ("ACTIVE_OLLAMA_MODEL", "llama3.2"),
    ("CHANNEL_COOLDOWNS", {}),
    ("ALLOWED_PERSONALITY_USERS", []),
]:
    if key not in config_data:
        config_data[key] = default
        save_config()

# --- CLIENTS ---
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE
VERTEX_PROJECT = "cloudstore-c1b65"
VERTEX_LOCATION = "us-central1"

gemini_client = None
try:
    gemini_client = genai.Client(vertexai=True, project=VERTEX_PROJECT, location=VERTEX_LOCATION)
    print(f"Vertex AI Client initialized (Project: {VERTEX_PROJECT}, Location: {VERTEX_LOCATION})")
except Exception as e:
    print(f"Failed to initialize Vertex AI Client: {e}")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
lyria_client = None
if GEMINI_API_KEY:
    try:
        lyria_client = genai.Client(api_key=GEMINI_API_KEY)
        print("Lyria Client (AI Studio) initialized for song generation")
    except Exception as e:
        print(f"Failed to initialize Lyria Client: {e}")

bot = commands.Bot(command_prefix=COMMAND_PREFIX, self_bot=True)

AI_MARKER = "\u200b\u200c"

async def safe_reply(message, content=None, **kwargs):
    if content is None:
        content = AI_MARKER
    else:
        content = str(content) + AI_MARKER
    try:
        return await message.reply(content=content, **kwargs)
    except discord.errors.HTTPException:
        fallback = f"<@{message.author.id}> {content}" if content else f"<@{message.author.id}>"
        return await message.channel.send(content=fallback, **kwargs)
    except Exception as e:
        print(f"Unexpected error in safe_reply: {e}")
        return None

def fmt_uptime(seconds: float) -> str:
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

def load_global_memories() -> list[str]:
    if not os.path.exists(GLOBAL_MEMORY_FILE):
        return []
    try:
        with open(GLOBAL_MEMORY_FILE, "r", encoding="utf-8") as f:
            return [line.strip().lstrip("- ").strip() for line in f if line.strip()]
    except:
        return []

def save_global_memories(memories: list[str]):
    with open(GLOBAL_MEMORY_FILE, "w", encoding="utf-8") as f:
        for m in memories:
            f.write(f"- {m}\n")

def load_user_memories() -> dict:
    if not os.path.exists(USER_MEMORIES_FILE):
        return {}
    try:
        with open(USER_MEMORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_user_memories(data: dict):
    with open(USER_MEMORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_user_personalities() -> dict:
    if not os.path.exists(PERSONALITIES_FILE):
        return {}
    try:
        with open(PERSONALITIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_user_personalities(data: dict):
    with open(PERSONALITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_user_personality(user_id: int) -> str:
    """Returns the personality text for a specific user, or empty string."""
    data = load_user_personalities()
    return data.get(str(user_id), "").strip()

def set_user_personality(user_id: int, text: str):
    data = load_user_personalities()
    data[str(user_id)] = text.strip()
    save_user_personalities(data)

def clear_user_personality(user_id: int):
    data = load_user_personalities()
    data.pop(str(user_id), None)
    save_user_personalities(data)

def get_effective_cooldown(channel_id: int) -> float:
    """Returns channel-specific cooldown if set, otherwise global cooldown."""
    channel_cooldowns = config_data.get("CHANNEL_COOLDOWNS", {})
    return channel_cooldowns.get(str(channel_id), config_data.get("COOLDOWN_SECONDS", 5))

# ---------------------------------------------------------
# RANDOM MESSAGE POOLS
# ---------------------------------------------------------

IMAGE_START_MSGS = [
    "Lemme paint ts 😭🙏", "Hold on, cooking up a masterpiece 👨‍🎨",
    "Generating your image blud... ⏳", "Gotchu, drawing this rn 🖌️",
    "Say less, painting it right now 🎨", "AI canvas is warming up 🖼️",
    "Aight, finna turn into Picasso 🧑‍🎨", "Hold up, let me visualize this 🧠"
]
IMAGE_DONE_MSGS = [
    "Heres yo image blud 🤑", "Ts goes hard ngl 🔥", "Done painting this for u 🎨",
    "Masterpiece completed 🖼️", "Fresh out the AI oven 🥖",
    "Look at this perfection 🤌", "Bro this actually looks insane 💀"
]
VIDEO_START_MSGS = [
    "Lemme cook up this video ts 🎬 (this takes some minutes)",
    "Directing your movie rn 🎥 (gimme a few mins)",
    "Generating video... grab some popcorn 🍿",
    "Cooking up the visuals, hold tight 🎞️",
    "Action! AI is rendering the scene 📽️",
    "Patience blud, making a whole movie here 🎬"
]
VIDEO_DONE_MSGS = [
    "Here is your video blud 🎥", "Movie is ready, ts is crazy 🎬",
    "Done rendering your clip 🎞️", "Here you go, Spielberg 🍿",
    "Ts belongs in a cinema 🎞️", "Final cut is ready 🔥"
]
VIDEO_LARGE_MSGS = [
    "Video generated but it is large. Downloading from Cloud URI... ⏳",
    "File is massive, pulling it from the cloud rn ☁️",
    "Hold on, downloading the big file... 📡",
    "Ts too heavy, fetching from server 🏋️‍♂️"
]
SONG_START_MSGS = [
    "Lemme cook up this song 🎵 (hold on)",
    "Producing your track rn 🎧 (wait a sec)",
    "Making beats for you... 🎹",
    "Tuning the instruments, gimme a sec 🎸",
    "Finna drop a platinum hit 💿",
    "Studio time, let me cook 🎙️"
]
SONG_DONE_MSGS = [
    "Here is your song blud 🎶", "Track is ready, ts is a banger 🎧",
    "Done producing your audio 🔊", "Grammy winning track right here 🏆",
    "Straight out the AI studio 🎙️", "This beat goes crazy 🔥"
]
ERROR_MSGS = [
    "Nah fam, ts was too hard: {e}", "Bro broke the API: {e} 💀",
    "My bad gng, error: {e} 🥀", "Aint no way, something failed: {e} 📉",
    "I'm cooked, got an error: {e} 😭", "The matrix broke: {e} 🛑"
]

# ---------------------------------------------------------
# BOT EVENTS
# ---------------------------------------------------------

@bot.event
async def on_ready():
    print(f'Successfully logged in as {bot.user} (ID: {bot.user.id})')
    print('--------------------------------------------------')
    print(f'Prefix: {COMMAND_PREFIX}')
    print(f'{COMMAND_PREFIX}self <prompt>          — Talk to the AI (ignores self pings)')
    print(f'{COMMAND_PREFIX}backend [gemini/ollama] — Switch AI engine')
    print(f'{COMMAND_PREFIX}models list/set <model> — Manage active model')
    print(f'{COMMAND_PREFIX}status                  — Show status of all services + uptime')
    print(f'{COMMAND_PREFIX}personality <text>      — Set your personal AI personality (DMs only, requires permission)')
    print(f'{COMMAND_PREFIX}personality clear        — Clear your personal personality')
    print(f'{COMMAND_PREFIX}personality view [@user] — View a personality (own = anyone, others = bot owner)')
    print(f'{COMMAND_PREFIX}user allow/deny <@user> personality — Grant/revoke personality permission')
    print(f'{COMMAND_PREFIX}remember <@user?> <text>— Save a memory')
    print(f'{COMMAND_PREFIX}memories                — show help + all subcommands')
    print(f'{COMMAND_PREFIX}memories all            — show all memories')
    print(f'{COMMAND_PREFIX}memories user [@user]   — show user memories')
    print(f'{COMMAND_PREFIX}memories global         — show global memories')
    print(f'{COMMAND_PREFIX}memories delete all     — wipe ALL memories')
    print(f'{COMMAND_PREFIX}memories delete global [i] — delete global memory by index')
    print(f'{COMMAND_PREFIX}memories delete user <@u> [i] — delete user memory by index')
    print(f'{COMMAND_PREFIX}channel status          — Check if current channel is allowed')
    print(f'{COMMAND_PREFIX}channel add [id]        — Add channel to allowed list')
    print(f'{COMMAND_PREFIX}channel remove [id]     — Remove channel from allowed list')
    print(f'{COMMAND_PREFIX}channel cooldown <s/false> [id] — Set/remove channel cooldown')
    print(f'{COMMAND_PREFIX}image <prompt>          — Generate image')
    print(f'{COMMAND_PREFIX}video <prompt>          — Generate video')
    print(f'{COMMAND_PREFIX}song <prompt>           — Generate song')
    print(f'{COMMAND_PREFIX}user info/ban/unban/allow/deny — User management')
    print(f'{COMMAND_PREFIX}toggle [image/video/song]— Enable/disable features globally')
    print(f'{COMMAND_PREFIX}byebye                  — Stop the bot')
    print(f'{COMMAND_PREFIX}refresh                 — Restart the bot')
    print('--------------------------------------------------')

    if os.path.exists(REFRESH_FILE):
        try:
            with open(REFRESH_FILE, "r") as f:
                channel_id = int(f.read().strip())
            os.remove(REFRESH_FILE)
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send("back" + AI_MARKER, delete_after=5)
        except:
            pass

@bot.event
async def on_message(message):
    global last_response_time

    if message.author.id in config_data.get("BANNED_USERS", []):
        return

    features = config_data.get("FEATURES", {})
    backend = config_data.get("AI_BACKEND", "gemini")
    is_dm = isinstance(message.channel, discord.DMChannel)

    if message.content.lower().startswith(f"{COMMAND_PREFIX}user info"):
        target = message.author
        if message.mentions and message.author.id == bot.user.id:
            target = message.mentions[0]
        is_banned = target.id in config_data.get("BANNED_USERS", [])
        can_img = target.id in config_data.get("ALLOWED_IMAGE_USERS", [])
        can_vid = target.id in config_data.get("ALLOWED_VIDEO_USERS", [])
        can_sng = target.id in config_data.get("ALLOWED_SONG_USERS", [])
        can_per = target.id in config_data.get("ALLOWED_PERSONALITY_USERS", [])
        has_per = bool(get_user_personality(target.id))
        msg = (f"**User Info for {target.name}**\n"
               f"**Banned:** {'Yes' if is_banned else 'No'}\n"
               f"**Image Gen:** {'Allowed' if can_img else 'Denied'}\n"
               f"**Video Gen:** {'Allowed' if can_vid else 'Denied'}\n"
               f"**Song Gen:** {'Allowed' if can_sng else 'Denied'}\n"
               f"**Personality:** {'Allowed' if can_per else 'Denied'} "
               f"{'(active)' if has_per else '(not set)'}")
        await safe_reply(message, content=msg, delete_after=5)
        return

    is_self_cmd = message.content.startswith(f"{COMMAND_PREFIX}self ")

    if message.author == bot.user and not is_self_cmd:
        await bot.process_commands(message)
        return

    if not is_dm:
        allowed_channels = config_data.get("ALLOWED_CHANNELS", [])
        if allowed_channels and message.channel.id not in allowed_channels:
            return

    if message.content.startswith(f"{COMMAND_PREFIX}image ") and message.author.id in config_data.get("ALLOWED_IMAGE_USERS", []):
        if not features.get("IMAGE_ENABLED", True):
            await safe_reply(message, content="Cant create an image rn.")
            return
        prompt = message.content[len(f"{COMMAND_PREFIX}image "):].strip()
        if prompt:
            await process_image_request(message, prompt)
            return

    if message.content.startswith(f"{COMMAND_PREFIX}video ") and message.author.id in config_data.get("ALLOWED_VIDEO_USERS", []):
        if not features.get("VIDEO_ENABLED", True):
            await safe_reply(message, content="Cant create a video rn.")
            return
        prompt = message.content[len(f"{COMMAND_PREFIX}video "):].strip()
        if prompt:
            await process_video_request(message, prompt)
            return

    if message.content.startswith(f"{COMMAND_PREFIX}song ") and message.author.id in config_data.get("ALLOWED_SONG_USERS", []):
        if not features.get("SONG_ENABLED", True):
            await safe_reply(message, content="Cant create a song rn.")
            return
        prompt = message.content[len(f"{COMMAND_PREFIX}song "):].strip()
        if prompt:
            await process_song_request(message, prompt)
            return

    if bot.user not in message.mentions and not is_self_cmd:
        await bot.process_commands(message)
        return

    if is_dm and not is_self_cmd and message.author == bot.user:
        await bot.process_commands(message)
        return

    current_time = time.time()
    channel_id = message.channel.id
    effective_cooldown = get_effective_cooldown(channel_id)
    channel_last = last_channel_response_times.get(channel_id, 0)

    if current_time - channel_last < effective_cooldown:
        return

    if is_self_cmd:
        user_msg = message.content[len(f"{COMMAND_PREFIX}self "):].strip()
    elif is_dm:
        user_msg = message.content.strip()
    else:
        user_msg = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()

    if not user_msg:
        return

    context = "[METADATA]\n"
    context += f"Sender: {message.author.display_name} (Username: {message.author.name})\n"
    if message.guild:
        context += f"Server: {message.guild.name} | Channel: {message.channel.name}\n"
    else:
        context += "Location: Direct Message\n"
    context += f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    chat_history = ""
    try:
        history_msgs = []
        async for hist_msg in message.channel.history(limit=message_context_limit + 1, before=message):
            history_msgs.append(hist_msg)
        history_msgs.reverse()
        for hist_msg in history_msgs:
            author_name = hist_msg.author.display_name
            clean_content = hist_msg.content.replace(AI_MARKER, '')
            clean_content = clean_content.replace(f'<@{bot.user.id}>', f'@{bot.user.name}').replace(f'<@!{bot.user.id}>', f'@{bot.user.name}')
            if clean_content.startswith(f"{COMMAND_PREFIX}self "):
                clean_content = clean_content[len(f"{COMMAND_PREFIX}self "):].strip()
            if clean_content.strip():
                chat_history += f"{author_name}: {clean_content}\n"
    except:
        pass

    if chat_history:
        context += f"[RECENT CHAT HISTORY]\n{chat_history}\n"

    prompt = f"{context}[CURRENT MESSAGE]\n{user_msg}"

    last_channel_response_times[channel_id] = current_time
    last_response_time = current_time

    try:
        avatar_bytes = None
        avatar_mime = "image/png"
        if message.author.avatar:
            avatar_bytes = await message.author.avatar.read()
            avatar_mime = "image/gif" if message.author.avatar.is_animated() else "image/png"
        elif message.author.default_avatar:
            avatar_bytes = await message.author.default_avatar.read()

        att_bytes_list = []
        for attachment in message.attachments:
            if attachment.content_type and ("image" in attachment.content_type or "video" in attachment.content_type):
                try:
                    b = await attachment.read()
                    att_bytes_list.append({"bytes": b, "mime": attachment.content_type})
                except:
                    pass

        sys_instruct = ""

        personality = get_user_personality(message.author.id)
        if personality:
            sys_instruct += f"[PERSONALITY set by this user]\n{personality}\n\n"

        if os.path.exists(INSTRUCTIONS_FILE):
            with open(INSTRUCTIONS_FILE, "r", encoding="utf-8") as f:
                sys_instruct += f.read().strip()

        if is_dm:
            sys_instruct += ("\n\n[DM MODE] You are in a private direct message. "
                             "You may be more relaxed, casual, and personal here. "
                             "You can drop some formality and speak more freely — "
                             "but still stay sensible and don't cross ethical lines.")

        global_mems_list = load_global_memories()
        if global_mems_list:
            sys_instruct += "\n\n[GLOBAL MEMORY]:\n" + "\n".join(f"- {m}" for m in global_mems_list)

        user_id_str = str(message.author.id)
        all_users_mem = load_user_memories()
        if user_id_str in all_users_mem and all_users_mem[user_id_str]:
            sys_instruct += f"\n\n[USER SPECIFIC MEMORY ({message.author.name})]:\n"
            for fact in all_users_mem[user_id_str]:
                sys_instruct += f"- {fact}\n"

        sys_instruct += "\n\nIMPORTANT — You have long-term memory. Check the provided memories above.\n"
        sys_instruct += "ADDING memories (append at the very end of your response):\n"
        sys_instruct += "  [GLOBALMEM: fact] — save a new global fact (only if NOT already stored)\n"
        sys_instruct += "  [USERMEM: fact]   — save a new fact about the current user (only if NOT already stored)\n"
        sys_instruct += "DELETING memories (append at the very end, when asked or when a memory is outdated/wrong):\n"
        sys_instruct += "  [DELMEM: exact fact text]       — delete a specific user memory\n"
        sys_instruct += "  [DELGLOBALMEM: exact fact text] — delete a specific global memory\n"
        sys_instruct += "Only use these tags at the very end of your response. Never duplicate an existing memory."

        can_image = features.get("IMAGE_ENABLED", True) and message.author.id in config_data.get("ALLOWED_IMAGE_USERS", [])
        can_video = features.get("VIDEO_ENABLED", True) and message.author.id in config_data.get("ALLOWED_VIDEO_USERS", [])
        can_song  = features.get("SONG_ENABLED", True)  and message.author.id in config_data.get("ALLOWED_SONG_USERS", [])

        if can_image or can_video or can_song:
            sys_instruct += "\n\nAUTO-MEDIA GENERATION: Only use these when EXPLICITLY requested:\n"
            if can_image:
                sys_instruct += "  [IMAGE: detailed image prompt in english]\n"
            if can_video:
                sys_instruct += "  [VIDEO: detailed video prompt in english]\n"
            if can_song:
                sys_instruct += "  [SONG: detailed song/music prompt in english]\n"
            sys_instruct += "Use only ONE media tag per message. Place it at the very end."

        reply_text = ""

        if backend == "ollama":
            ollama_url = "http://localhost:11434/api/chat"
            messages = []
            if sys_instruct:
                messages.append({"role": "system", "content": sys_instruct})
            b64_images = []
            if avatar_bytes:
                b64_images.append(base64.b64encode(avatar_bytes).decode('utf-8'))
            for att in att_bytes_list:
                if "image" in att["mime"]:
                    b64_images.append(base64.b64encode(att["bytes"]).decode('utf-8'))
            user_payload = {"role": "user", "content": prompt}
            if b64_images:
                user_payload["images"] = b64_images
            messages.append(user_payload)
            active_ollama_model = config_data.get("ACTIVE_OLLAMA_MODEL", "llama3.2")
            payload = {"model": active_ollama_model, "messages": messages, "stream": False}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(ollama_url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            reply_text = data.get("message", {}).get("content", "")
                        else:
                            reply_text = f"Ollama Error ({resp.status}): Make sure Ollama is running and model '{active_ollama_model}' is pulled."
            except aiohttp.ClientConnectorError:
                reply_text = "Connection refused: Ollama is not running on localhost:11434"
            except Exception as e:
                reply_text = f"Local Ollama failed: {e}"
        else:
            if not gemini_client:
                reply_text = "Vertex AI Client is not initialized."
            else:
                contents_list = []
                if avatar_bytes:
                    contents_list.append(types.Part.from_bytes(data=avatar_bytes, mime_type=avatar_mime))
                for att in att_bytes_list:
                    contents_list.append(types.Part.from_bytes(data=att["bytes"], mime_type=att["mime"]))
                contents_list.append(prompt)
                config_kwargs = {}
                if sys_instruct:
                    config_kwargs['config'] = types.GenerateContentConfig(system_instruction=sys_instruct)
                active_model = config_data.get("ACTIVE_MODEL", "gemini-2.5-flash")
                response = await gemini_client.aio.models.generate_content(
                    model=active_model,
                    contents=contents_list,
                    **config_kwargs
                )
                reply_text = response.text

        for mem in re.findall(r'\[GLOBALMEM:\s*(.*?)\]', reply_text):
            m = mem.strip()
            if m:
                existing = load_global_memories()
                if m not in existing:
                    existing.append(m)
                    save_global_memories(existing)
        reply_text = re.sub(r'\[GLOBALMEM:\s*.*?\]', '', reply_text).strip()

        for mem in re.findall(r'\[USERMEM:\s*(.*?)\]', reply_text):
            m = mem.strip()
            if m:
                all_mem = load_user_memories()
                uid = str(message.author.id)
                if uid not in all_mem:
                    all_mem[uid] = []
                if m not in all_mem[uid]:
                    all_mem[uid].append(m)
                    save_user_memories(all_mem)
        reply_text = re.sub(r'\[USERMEM:\s*.*?\]', '', reply_text).strip()

        for mem in re.findall(r'\[DELMEM:\s*(.*?)\]', reply_text):
            m = mem.strip()
            if m:
                all_mem = load_user_memories()
                uid = str(message.author.id)
                if uid in all_mem:
                    all_mem[uid] = [f for f in all_mem[uid] if m.lower() not in f.lower()]
                    save_user_memories(all_mem)
        reply_text = re.sub(r'\[DELMEM:\s*.*?\]', '', reply_text).strip()

        for mem in re.findall(r'\[DELGLOBALMEM:\s*(.*?)\]', reply_text):
            m = mem.strip()
            if m:
                existing = load_global_memories()
                existing = [f for f in existing if m.lower() not in f.lower()]
                save_global_memories(existing)
        reply_text = re.sub(r'\[DELGLOBALMEM:\s*.*?\]', '', reply_text).strip()

        image_match = re.search(r'\[IMAGE:\s*(.*?)\]', reply_text) or re.search(r'\[PAINT:\s*(.*?)\]', reply_text)
        video_match = re.search(r'\[VIDEO:\s*(.*?)\]', reply_text)
        song_match  = re.search(r'\[SONG:\s*(.*?)\]',  reply_text)

        if image_match:
            reply_text = re.sub(r'\[(?:IMAGE|PAINT):\s*.*?\]', '', reply_text).strip()
        if video_match:
            reply_text = re.sub(r'\[VIDEO:\s*.*?\]', '', reply_text).strip()
        if song_match:
            reply_text = re.sub(r'\[SONG:\s*.*?\]',  '', reply_text).strip()

    except Exception as e:
        reply_text = random.choice(ERROR_MSGS).format(e=e)
        image_match = video_match = song_match = None

    if reply_text:
        if len(reply_text) > 3900:
            file_obj = io.BytesIO(reply_text.encode('utf-8'))
            file = discord.File(file_obj, filename="ai_antwort.txt")
            await safe_reply(message, content="*Message exceeded 3900 characters, file attached*", file=file)
        else:
            await safe_reply(message, content=reply_text)

    if image_match and can_image:
        asyncio.create_task(process_image_request(message, image_match.group(1)))
    elif video_match and can_video:
        asyncio.create_task(process_video_request(message, video_match.group(1)))
    elif song_match and can_song:
        asyncio.create_task(process_song_request(message, song_match.group(1)))


async def process_image_request(message, prompt: str):
    if not gemini_client:
        print("Gemini client not initialized, cannot generate image.")
        return
    try:
        msg = await safe_reply(message, content=random.choice(IMAGE_START_MSGS))
        result = await gemini_client.aio.models.generate_images(
            model='imagen-4.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1, output_mime_type="image/jpeg")
        )
        if result.generated_images is None:
            if msg: await msg.edit(content="API didn't return an image (prompt might be blocked)." + AI_MARKER)
            return
        for generated_image in result.generated_images:
            file_obj = io.BytesIO(generated_image.image.image_bytes)
            file = discord.File(file_obj, filename="bild.jpeg")
            await safe_reply(message, content=random.choice(IMAGE_DONE_MSGS), file=file)
            break
        try:
            if msg: await msg.delete()
        except:
            pass
    except Exception as e:
        await safe_reply(message, content=random.choice(ERROR_MSGS).format(e=e))

async def process_video_request(message, prompt: str):
    if not gemini_client:
        return
    msg = await safe_reply(message, content=random.choice(VIDEO_START_MSGS))
    try:
        op = await gemini_client.aio.models.generate_videos(model='veo-2.0-generate-001', prompt=prompt)
        while not op.done:
            await asyncio.sleep(5)
            op = await gemini_client.aio.operations.get(operation=op)
        if op.error:
            err_msg = op.error.get('message', str(op.error)) if isinstance(op.error, dict) else getattr(op.error, 'message', str(op.error))
            if msg: await msg.edit(content=f"API Error: {err_msg}" + AI_MARKER)
            return
        final_result = getattr(op, 'result', getattr(op, 'response', None))
        if final_result and final_result.generated_videos:
            for generated_video in final_result.generated_videos:
                video_data = generated_video.video.video_bytes
                if (not video_data or len(video_data) == 0) and getattr(generated_video.video, 'uri', None):
                    if msg: await msg.edit(content=random.choice(VIDEO_LARGE_MSGS) + AI_MARKER)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(generated_video.video.uri) as resp:
                            if resp.status == 200:
                                video_data = await resp.read()
                            else:
                                if msg: await msg.edit(content=f"Error downloading Video. URI Status: {resp.status}" + AI_MARKER)
                                return
                if not video_data or len(video_data) == 0:
                    if msg: await msg.edit(content="API returned empty video (blocked or error)" + AI_MARKER)
                    return
                file_obj = io.BytesIO(video_data)
                file = discord.File(file_obj, filename="video.mp4")
                try:
                    await safe_reply(message, content=random.choice(VIDEO_DONE_MSGS), file=file)
                except Exception as e:
                    cloud_uri = getattr(generated_video.video, 'uri', 'N/A')
                    await safe_reply(message, content=f"Video too big ({len(video_data)/(1024*1024):.2f}MB). Download: {cloud_uri}")
                break
        else:
            if msg: await msg.edit(content="API didn't return any video (blocked?)" + AI_MARKER)
        try:
            if msg: await msg.delete()
        except:
            pass
    except Exception as e:
        await safe_reply(message, content=random.choice(ERROR_MSGS).format(e=e))

async def process_song_request(message, prompt: str):
    if not lyria_client:
        await safe_reply(message, content="Cant make songs rn gng (no api key).")
        return
    msg = await safe_reply(message, content=random.choice(SONG_START_MSGS))
    try:
        response = await lyria_client.aio.models.generate_content(model='lyria-3-clip-preview', contents=prompt)
        audio_data = None
        lyrics_parts = []
        for part in (response.parts or []):
            if part.text is not None:
                lyrics_parts.append(part.text)
            elif part.inline_data is not None:
                audio_data = part.inline_data.data
        if not audio_data:
            if msg: await msg.edit(content="API didn't return any audio (blocked?)" + AI_MARKER)
            return
        file_obj = io.BytesIO(audio_data)
        file = discord.File(file_obj, filename="song.mp3")
        lyrics_text = "\n".join(lyrics_parts)
        if len(lyrics_text) > 1800:
            lyrics_text = lyrics_text[:1800] + "..."
        reply_content = random.choice(SONG_DONE_MSGS)
        if lyrics_text:
            reply_content += f"\n```\n{lyrics_text}\n```"
        await safe_reply(message, content=reply_content, file=file)
        try:
            if msg: await msg.delete()
        except:
            pass
    except Exception as e:
        await safe_reply(message, content=random.choice(ERROR_MSGS).format(e=e))

async def handle_list_toggle(ctx, list_key: str, action_name: str, add: bool):
    try:
        await ctx.message.delete()
    except:
        pass
    if not ctx.message.mentions:
        await ctx.send("You gotta ping someone" + AI_MARKER, delete_after=5)
        return
    user_id   = ctx.message.mentions[0].id
    user_name = ctx.message.mentions[0].name
    current_list = config_data.get(list_key, [])
    if add:
        if user_id not in current_list:
            current_list.append(user_id)
            config_data[list_key] = current_list
            save_config()
            await ctx.send(f"Successfully {action_name} ({user_name})" + AI_MARKER, delete_after=3)
        else:
            await ctx.send(f"{user_name} is already {action_name}" + AI_MARKER, delete_after=3)
    else:
        if user_id in current_list:
            current_list.remove(user_id)
            config_data[list_key] = current_list
            save_config()
            await ctx.send(f"Successfully removed {user_name} from {action_name}" + AI_MARKER, delete_after=3)
        else:
            await ctx.send(f"{user_name} is not {action_name}" + AI_MARKER, delete_after=3)

@bot.group(invoke_without_command=True)
async def user(ctx):
    try: await ctx.message.delete()
    except: pass
    await ctx.send(
        f"Usage:\n"
        f"`{COMMAND_PREFIX}user info [@user]`\n"
        f"`{COMMAND_PREFIX}user ban/unban <@user>`\n"
        f"`{COMMAND_PREFIX}user allow/deny <@user> <image/video/song>`" + AI_MARKER,
        delete_after=10
    )

@user.command(name="ban")
async def user_ban(ctx):
    await handle_list_toggle(ctx, "BANNED_USERS", "banned", add=True)

@user.command(name="unban")
async def user_unban(ctx):
    await handle_list_toggle(ctx, "BANNED_USERS", "banned", add=False)

@user.command(name="allow")
async def user_allow(ctx, *args):
    valid_perms = ["image", "video", "song", "personality"]
    # We look for the perm type in any of the provided arguments
    perm_type = next((x.lower() for x in args if x.lower() in valid_perms), None)

    if not perm_type:
        await ctx.send("Specify what to allow: `image`, `video`, `song`, or `personality`" + AI_MARKER, delete_after=5)
        return

    list_key = f"ALLOWED_{perm_type.upper()}_USERS"
    await handle_list_toggle(ctx, list_key, f"allowed to use {perm_type.lower()}", add=True)

@user.command(name="deny")
async def user_deny(ctx, *args):
    valid_perms = ["image", "video", "song", "personality"]
    perm_type = next((x.lower() for x in args if x.lower() in valid_perms), None)

    if not perm_type:
        await ctx.send("Specify what to deny: `image`, `video`, `song`, or `personality`" + AI_MARKER, delete_after=5)
        return

    list_key = f"ALLOWED_{perm_type.upper()}_USERS"
    await handle_list_toggle(ctx, list_key, f"allowed to use {perm_type.lower()}", add=False)

@bot.command()
async def toggle(ctx, feature: str = None):
    try: await ctx.message.delete()
    except: pass
    if not feature or feature.lower() not in ["image", "video", "song"]:
        await ctx.send("Specify what to toggle: `image`, `video`, or `song`" + AI_MARKER, delete_after=5)
        return
    feat_key = f"{feature.upper()}_ENABLED"
    features = config_data.setdefault("FEATURES", {})
    new_state = not features.get(feat_key, True)
    features[feat_key] = new_state
    save_config()
    state_str = "ENABLED" if new_state else "DISABLED"
    await ctx.send(f"Global feature `{feature}` is now {state_str}" + AI_MARKER, delete_after=5)

@bot.command()
async def backend(ctx, backend_name: str = None):
    try: await ctx.message.delete()
    except: pass
    if not backend_name or backend_name.lower() not in ["gemini", "ollama"]:
        current = config_data.get("AI_BACKEND", "gemini")
        await ctx.send(f"Current Backend: `{current}`\nUsage: `{COMMAND_PREFIX}backend [gemini|ollama]`" + AI_MARKER, delete_after=8)
        return
    config_data["AI_BACKEND"] = backend_name.lower()
    save_config()
    await ctx.send(f"AI Backend switched to `{backend_name.lower()}`" + AI_MARKER, delete_after=5)

@bot.command()
async def models(ctx, action: str = None, model_name: str = None):
    try: await ctx.message.delete()
    except: pass
    backend_val = config_data.get("AI_BACKEND", "gemini")
    if action == "list":
        if backend_val == "gemini":
            active = config_data.get("ACTIVE_MODEL", "gemini-2.5-flash")
            try:
                api_models = await gemini_client.aio.models.list()
                names = sorted(set(m.name.split('/')[-1] for m in api_models if "gemini" in m.name.lower()))
                msg = "**Available Models from Vertex (Gemini):**\n"
                for m in names:
                    marker = " ← active" if m == active else ""
                    msg += f"- `{m}`{marker}\n"
                await ctx.send(msg + AI_MARKER, delete_after=15)
            except Exception as e:
                await ctx.send(f"Error fetching Vertex models: {e}" + AI_MARKER, delete_after=5)
        elif backend_val == "ollama":
            active = config_data.get("ACTIVE_OLLAMA_MODEL", "llama3.2")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:11434/api/tags") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            names = [m["name"] for m in (data.get("models") or [])]
                            msg = "**Available Local Models (Ollama):**\n"
                            for m in names:
                                marker = " ← active" if m == active else ""
                                msg += f"- `{m}`{marker}\n"
                            await ctx.send(msg + AI_MARKER, delete_after=15)
                        else:
                            await ctx.send("Ollama is not responding" + AI_MARKER, delete_after=5)
            except Exception as e:
                await ctx.send(f"Failed to connect to Ollama: {e}" + AI_MARKER, delete_after=5)
    elif action == "set":
        if not model_name:
            await ctx.send(f"Specify a model: `{COMMAND_PREFIX}models set <model>`" + AI_MARKER, delete_after=5)
            return
        if backend_val == "gemini":
            config_data["ACTIVE_MODEL"] = model_name
        else:
            config_data["ACTIVE_OLLAMA_MODEL"] = model_name
        save_config()
        await ctx.send(f"Active {backend_val} model set to `{model_name}`" + AI_MARKER, delete_after=5)
    else:
        await ctx.send(
            f"`{COMMAND_PREFIX}models list` — show models for current backend\n"
            f"`{COMMAND_PREFIX}models set <model>` — change active model" + AI_MARKER,
            delete_after=8
        )


@bot.command()
async def status(ctx):
    try: await ctx.message.delete()
    except: pass

    uptime_str = fmt_uptime(time.time() - start_time)
    backend_val = config_data.get("AI_BACKEND", "gemini")
    active_model = config_data.get("ACTIVE_MODEL", "gemini-2.5-flash")
    active_ollama = config_data.get("ACTIVE_OLLAMA_MODEL", "llama3.2")
    features = config_data.get("FEATURES", {})

    vertex_status = "Initialized" if gemini_client else "Not initialized"

    lyria_status = "Initialized" if lyria_client else "No API Key / Not initialized"

    ollama_status = "Checking..."
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:11434/api/tags", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    model_count = len(data.get("models") or [])
                    ollama_status = f"Running ({model_count} model{'s' if model_count != 1 else ''} pulled)"
                else:
                    ollama_status = f"Responded with status {resp.status}"
    except:
        ollama_status = "Not running (localhost:11434)"


    allowed = config_data.get("ALLOWED_CHANNELS", [])
    channel_info = f"{len(allowed)} channel(s) whitelisted" if allowed else "All channels (no filter)"

    global_cd = config_data.get("COOLDOWN_SECONDS", 5)
    channel_cds = config_data.get("CHANNEL_COOLDOWNS", {})
    cd_info = f"{global_cd}s global"
    if channel_cds:
        cd_info += f", {len(channel_cds)} channel override(s)"

    msg = (
        f"**Bot Status**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱**Uptime:** {uptime_str}\n"
        f"**Backend:** `{backend_val}`\n"
        f"**Active Gemini Model:** `{active_model}`\n"
        f"**Active Ollama Model:** `{active_ollama}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Services:**\n"
        f"  Vertex AI:  {vertex_status}\n"
        f"  Lyria:      {lyria_status}\n"
        f"  Ollama:     {ollama_status}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Features:**\n"
        f"  🖼️ Image: {'true' if features.get('IMAGE_ENABLED', True) else 'false'} "
        f"  🎬 Video: {'true' if features.get('VIDEO_ENABLED', True) else 'false'} "
        f"  🎵 Song: {'true' if features.get('SONG_ENABLED', True) else 'false'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Channels:** {channel_info}\n"
        f"**Cooldown:** {cd_info}"
    )
    await ctx.send(msg + AI_MARKER, delete_after=20)

@bot.group(invoke_without_command=True)
async def channel(ctx):
    try: await ctx.message.delete()
    except: pass
    await ctx.send(
        f"**Channel commands:**\n"
        f"`{COMMAND_PREFIX}channel status` — is this channel allowed?\n"
        f"`{COMMAND_PREFIX}channel add [id]` — add channel to whitelist\n"
        f"`{COMMAND_PREFIX}channel remove [id]` — remove from whitelist\n"
        f"`{COMMAND_PREFIX}channel cooldown <seconds/false> [channel_id]` — set/remove cooldown" + AI_MARKER,
        delete_after=12
    )

def _resolve_channel_id(ctx, arg: str = None) -> int | None:
    """Resolve a channel ID from an argument string or fall back to ctx.channel.id."""
    if arg:

        ch_mention = re.match(r'<#(\d+)>', arg)
        if ch_mention:
            return int(ch_mention.group(1))

        try:
            return int(arg)
        except ValueError:
            return None
    return ctx.channel.id

@channel.command(name="status")
async def channel_status(ctx, channel_id_arg: str = None):
    try: await ctx.message.delete()
    except: pass
    ch_id = _resolve_channel_id(ctx, channel_id_arg)
    if ch_id is None:
        await ctx.send("Invalid channel ID." + AI_MARKER, delete_after=5)
        return
    allowed = config_data.get("ALLOWED_CHANNELS", [])
    ch_cooldown = config_data.get("CHANNEL_COOLDOWNS", {}).get(str(ch_id))
    global_cd = config_data.get("COOLDOWN_SECONDS", 5)

    if not allowed:
        status_str = "Allowed (no whitelist — bot responds everywhere)"
    elif ch_id in allowed:
        status_str = "Allowed (in whitelist)"
    else:
        status_str = "NOT allowed (not in whitelist)"

    cd_str = f"{ch_cooldown}s (channel override)" if ch_cooldown is not None else f"{global_cd}s (global)"

    await ctx.send(
        f"**Channel `{ch_id}`**\n"
        f"Status: {status_str}\n"
        f"Cooldown: {cd_str}" + AI_MARKER,
        delete_after=10
    )

@channel.command(name="add")
async def channel_add(ctx, channel_id_arg: str = None):
    try: await ctx.message.delete()
    except: pass
    ch_id = _resolve_channel_id(ctx, channel_id_arg)
    if ch_id is None:
        await ctx.send("Invalid channel ID." + AI_MARKER, delete_after=5)
        return
    allowed = config_data.setdefault("ALLOWED_CHANNELS", [])
    if ch_id not in allowed:
        allowed.append(ch_id)
        save_config()
        await ctx.send(f"Channel `{ch_id}` added to whitelist" + AI_MARKER, delete_after=5)
    else:
        await ctx.send(f"Channel `{ch_id}` is already in the whitelist" + AI_MARKER, delete_after=5)

@channel.command(name="remove")
async def channel_remove(ctx, channel_id_arg: str = None):
    try: await ctx.message.delete()
    except: pass
    ch_id = _resolve_channel_id(ctx, channel_id_arg)
    if ch_id is None:
        await ctx.send("Invalid channel ID." + AI_MARKER, delete_after=5)
        return
    allowed = config_data.get("ALLOWED_CHANNELS", [])
    if ch_id in allowed:
        allowed.remove(ch_id)
        save_config()
        await ctx.send(f"Channel `{ch_id}` removed from whitelist" + AI_MARKER, delete_after=5)
    else:
        await ctx.send(f"Channel `{ch_id}` wasn't in the whitelist" + AI_MARKER, delete_after=5)

@channel.command(name="cooldown")
async def channel_cooldown(ctx, value: str = None, channel_id_arg: str = None):
    try: await ctx.message.delete()
    except: pass
    if not value:
        await ctx.send(
            f"Usage:\n"
            f"`{COMMAND_PREFIX}channel cooldown <seconds> [channel_id]` — set cooldown\n"
            f"`{COMMAND_PREFIX}channel cooldown false [channel_id]` — remove cooldown override" + AI_MARKER,
            delete_after=8
        )
        return
    ch_id = _resolve_channel_id(ctx, channel_id_arg)
    if ch_id is None:
        await ctx.send("Invalid channel ID." + AI_MARKER, delete_after=5)
        return
    channel_cds = config_data.setdefault("CHANNEL_COOLDOWNS", {})
    if value.lower() in ("false", "none", "off", "remove", "0"):
        if str(ch_id) in channel_cds:
            del channel_cds[str(ch_id)]
            save_config()
            await ctx.send(f"Channel-specific cooldown for `{ch_id}` removed — using global cooldown now" + AI_MARKER, delete_after=5)
        else:
            await ctx.send(f"No channel-specific cooldown was set for `{ch_id}`" + AI_MARKER, delete_after=5)
    else:
        try:
            seconds = float(value)
            if seconds < 0:
                raise ValueError
        except ValueError:
            await ctx.send("Cooldown must be a positive number or `false`." + AI_MARKER, delete_after=5)
            return
        channel_cds[str(ch_id)] = seconds
        save_config()
        await ctx.send(f"Cooldown for channel `{ch_id}` set to `{seconds}s`" + AI_MARKER, delete_after=5)


@bot.group(invoke_without_command=True)
async def memories(ctx):
    try: await ctx.message.delete()
    except: pass
    await ctx.send(
        f"**Memory commands:**\n"
        f"**— View —**\n"
        f"`{COMMAND_PREFIX}memories all` — show everything (global + all users)\n"
        f"`{COMMAND_PREFIX}memories global` — show global memories\n"
        f"`{COMMAND_PREFIX}memories user [@user]` — show user memories (own = anyone)\n"
        f"**— Delete —**\n"
        f"`{COMMAND_PREFIX}memories delete all` — wipe ALL memories\n"
        f"`{COMMAND_PREFIX}memories delete global [index]` — delete all/one global memory\n"
        f"`{COMMAND_PREFIX}memories delete user <@user> [index]` — delete all/one user memory" + AI_MARKER,
        delete_after=15
    )

def _format_memory_list(items: list[str], label: str) -> str:
    if not items:
        return f"**{label}:** *(empty)*\n"
    out = f"**{label}:**\n"
    for i, item in enumerate(items, 1):
        out += f"  `{i}.` {item}\n"
    return out

async def _send_memory_text(ctx, text: str, filename: str):
    if len(text) > 1900:
        file_obj = io.BytesIO(text.encode())
        await ctx.send("Too long, see file:" + AI_MARKER, file=discord.File(file_obj, filename), delete_after=30)
    else:
        await ctx.send(text + AI_MARKER, delete_after=30)

@memories.command(name="global")
async def memories_global(ctx):
    try: await ctx.message.delete()
    except: pass
    mems = load_global_memories()
    await _send_memory_text(ctx, _format_memory_list(mems, "Global Memories"), "global_memories.txt")

@memories.command(name="user")
async def memories_user(ctx, target: discord.Member = None):
    try: await ctx.message.delete()
    except: pass
    if target is None:
        target = ctx.author
    uid = str(target.id)
    user_mems = load_user_memories().get(uid, [])
    await _send_memory_text(ctx, _format_memory_list(user_mems, f"Memories for {target.name}"), "user_memories.txt")

@memories.command(name="all")
async def memories_all(ctx):
    try: await ctx.message.delete()
    except: pass
    global_mems = load_global_memories()
    all_mem = load_user_memories()
    text = _format_memory_list(global_mems, "Global Memories") + "\n"
    if all_mem:
        text += "**User Memories:**\n"
        for uid, facts in all_mem.items():
            text += f"  *User ID {uid}:*\n"
            for i, fact in enumerate(facts, 1):
                text += f"    `{i}.` {fact}\n"
    else:
        text += "**👥 User Memories:** *(empty)*"
    await _send_memory_text(ctx, text, "all_memories.txt")

@memories.group(name="delete", invoke_without_command=True)
async def memories_delete(ctx):
    try: await ctx.message.delete()
    except: pass
    await ctx.send(
        f"**Delete commands:**\n"
        f"`{COMMAND_PREFIX}memories delete all` — wipe ALL memories\n"
        f"`{COMMAND_PREFIX}memories delete global [index]` — delete all or one global memory\n"
        f"`{COMMAND_PREFIX}memories delete user <@user> [index]` — delete all or one user memory\n"
        f"*(Run `{COMMAND_PREFIX}memories global` or `memories user` first to see indexes)*" + AI_MARKER,
        delete_after=12
    )

@memories_delete.command(name="all")
async def memories_delete_all(ctx):
    try: await ctx.message.delete()
    except: pass
    if os.path.exists(GLOBAL_MEMORY_FILE):
        os.remove(GLOBAL_MEMORY_FILE)
    if os.path.exists(USER_MEMORIES_FILE):
        os.remove(USER_MEMORIES_FILE)
    await ctx.send("Every memorie got deleted" + AI_MARKER, delete_after=3)

@memories_delete.command(name="global")
async def memories_delete_global(ctx, index: str = None):
    try: await ctx.message.delete()
    except: pass
    mems = load_global_memories()
    if not mems:
        await ctx.send("No global memories to delete" + AI_MARKER, delete_after=5)
        return
    if index is None:
        save_global_memories([])
        await ctx.send("All global memories deleted" + AI_MARKER, delete_after=3)
    else:
        try:
            idx = int(index) - 1
            if idx < 0 or idx >= len(mems):
                raise ValueError
        except ValueError:
            await ctx.send(f"Invalid index. Use 1–{len(mems)}." + AI_MARKER, delete_after=5)
            return
        removed = mems.pop(idx)
        save_global_memories(mems)
        await ctx.send(f"Deleted global memory #{idx+1}: *{removed}*" + AI_MARKER, delete_after=5)

@memories_delete.command(name="user")
async def memories_delete_user(ctx, target: discord.Member = None, index: str = None):
    try: await ctx.message.delete()
    except: pass
    if target is None:
        await ctx.send("Ping someone to use this command" + AI_MARKER, delete_after=5)
        return
    uid = str(target.id)
    all_mem = load_user_memories()
    user_mems = all_mem.get(uid, [])
    if not user_mems:
        await ctx.send(f"No memories for {target.name}" + AI_MARKER, delete_after=5)
        return
    if index is None:
        all_mem[uid] = []
        save_user_memories(all_mem)
        await ctx.send(f"All memories for {target.name} deleted" + AI_MARKER, delete_after=3)
    else:
        try:
            idx = int(index) - 1
            if idx < 0 or idx >= len(user_mems):
                raise ValueError
        except ValueError:
            await ctx.send(f"Invalid index. Use 1–{len(user_mems)}." + AI_MARKER, delete_after=5)
            return
        removed = user_mems.pop(idx)
        all_mem[uid] = user_mems
        save_user_memories(all_mem)
        await ctx.send(f"Deleted memory #{idx+1} for {target.name}: *{removed}*" + AI_MARKER, delete_after=5)

@bot.command()
async def remember(ctx, *, text: str):
    try: await ctx.message.delete()
    except: pass
    mentions = ctx.message.mentions
    if mentions:
        target_user = mentions[0]
        fact = text.replace(f'<@{target_user.id}>', '').replace(f'<@!{target_user.id}>', '').strip()
        uid = str(target_user.id)
        all_mem = load_user_memories()
        if uid not in all_mem:
            all_mem[uid] = []
        if fact and fact not in all_mem[uid]:
            all_mem[uid].append(fact)
            save_user_memories(all_mem)
        try:
            await ctx.send(f"K gng ill remember dat for {target_user.name}" + AI_MARKER, delete_after=3)
        except:
            pass
    else:
        existing = load_global_memories()
        if text.strip() not in existing:
            existing.append(text.strip())
            save_global_memories(existing)
        try:
            await ctx.send("K gng ill remember dat globally" + AI_MARKER, delete_after=3)
        except:
            pass

@bot.group(invoke_without_command=True, name="personality")
async def personality_group(ctx, *, text: str = None):
    try: await ctx.message.delete()
    except: pass

    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(
            "Personality can only be set in DMs\n"
            f"Slide into my DMs and use `{COMMAND_PREFIX}personality <your text>`" + AI_MARKER,
            delete_after=6
        )
        return

    allowed = config_data.get("ALLOWED_PERSONALITY_USERS", [])
    if ctx.author.id != bot.user.id and ctx.author.id not in allowed:
        await ctx.send(
            "You don't have permission to set a personality\n"
            f"Ask the bot owner to run `{COMMAND_PREFIX}user allow @you personality`." + AI_MARKER,
            delete_after=6
        )
        return

    if not text or text.strip().lower() == "clear":
        clear_user_personality(ctx.author.id)
        await ctx.send("Your personality has been cleared. Back to default vibes" + AI_MARKER, delete_after=5)
        return

    set_user_personality(ctx.author.id, text.strip())
    preview = text.strip()[:100] + ("..." if len(text.strip()) > 100 else "")
    await ctx.send(
        f"Your personal personality is set!\n"
        f"The AI will act like:\n*{preview}*\n\n"
        f"*(Use `{COMMAND_PREFIX}personality clear` to reset)*" + AI_MARKER,
        delete_after=12
    )

@personality_group.command(name="clear")
async def personality_clear(ctx):
    try: await ctx.message.delete()
    except: pass
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("Use this in DMs 🔒" + AI_MARKER, delete_after=5)
        return
    clear_user_personality(ctx.author.id)
    await ctx.send("Your personality cleared. Back to default" + AI_MARKER, delete_after=5)

@personality_group.command(name="view")
async def personality_view(ctx, target: discord.Member = None):
    try: await ctx.message.delete()
    except: pass
    # Anyone can view their own; only bot owner can view others
    if target is None or target.id == ctx.author.id:
        p = get_user_personality(ctx.author.id)
        if p:
            await ctx.send(f"**Your current personality:**\n```{p[:1500]}```" + AI_MARKER, delete_after=15)
        else:
            await ctx.send("You haven't set a personality yet" + AI_MARKER, delete_after=5)
    elif ctx.author.id == bot.user.id:
        p = get_user_personality(target.id)
        if p:
            await ctx.send(f"**Personality for {target.name}:**\n```{p[:1500]}```" + AI_MARKER, delete_after=15)
        else:
            await ctx.send(f"{target.name} has no personality set." + AI_MARKER, delete_after=5)
    else:
        await ctx.send("You can only view your own personality 🔒" + AI_MARKER, delete_after=5)

# ---------------------------------------------------------
# COMMANDS — MEDIA (standalone commands)
# ---------------------------------------------------------

@bot.command()
async def image(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send(f"Use it like: `{COMMAND_PREFIX}image [prompt]`" + AI_MARKER, delete_after=5)
        return
    await process_image_request(ctx.message, prompt)

@bot.command()
async def video(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send(f"Use it like: `{COMMAND_PREFIX}video [prompt]`" + AI_MARKER, delete_after=5)
        return
    await process_video_request(ctx.message, prompt)

@bot.command()
async def song(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send(f"Use it like: `{COMMAND_PREFIX}song [prompt]`" + AI_MARKER, delete_after=5)
        return
    await process_song_request(ctx.message, prompt)

# ---------------------------------------------------------
# COMMANDS — BOT CONTROL
# ---------------------------------------------------------

@bot.command()
async def bye(ctx):
    print(f"Bot stopped via {COMMAND_PREFIX}bye")
    try:
        await ctx.message.delete()
        await ctx.send("Bye bye" + AI_MARKER, delete_after=2)
    except:
        pass
    await bot.close()

@bot.command()
async def refresh(ctx):
    with open(REFRESH_FILE, "w") as f:
        f.write(str(ctx.channel.id))
    try:
        await ctx.message.delete()
        await ctx.send("brb" + AI_MARKER, delete_after=3)
    except:
        pass
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.command()
async def purge(ctx, amount: int = 10, scope: str = "channel"):
    try: await ctx.message.delete()
    except: pass
    deleted = 0
    limit_scan = 1000
    allowed_channels = config_data.get("ALLOWED_CHANNELS", [])
    if scope == "all" and allowed_channels:
        for ch_id in allowed_channels:
            ch = bot.get_channel(ch_id)
            if ch:
                try:
                    async for msg in ch.history(limit=limit_scan):
                        if msg.author.id == bot.user.id and msg.content.endswith(AI_MARKER):
                            try:
                                await msg.delete()
                                deleted += 1
                                await asyncio.sleep(0.3)
                                if deleted >= amount:
                                    break
                            except:
                                pass
                except:
                    pass
            if deleted >= amount:
                break
    else:
        async for msg in ctx.channel.history(limit=limit_scan):
            if msg.author.id == bot.user.id and msg.content.endswith(AI_MARKER):
                try:
                    await msg.delete()
                    deleted += 1
                    await asyncio.sleep(0.3)
                    if deleted >= amount:
                        break
                except:
                    pass
    try:
        await ctx.send(f"{deleted} messages deleted" + AI_MARKER, delete_after=3)
    except:
        pass

# ---------------------------------------------------------
# EXECUTION
# ---------------------------------------------------------

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Error: No DISCORD_TOKEN found in .env file.")
    else:
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            print("Error: Invalid Token. Please check your User Token.")
        except Exception as e:
            print(f"An error occurred: {e}")