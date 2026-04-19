import sys
import subprocess
import os

# --- AUTOMATIC REQUIREMENTS INSTALLATION ---
def install_requirements():
    try:
        import discord
        import dotenv
        import aiohttp
        import google.genai
        return
    except ImportError:
        pass

    req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if os.path.exists(req_file):
        print("\n[!] IMPORTANT: Some dependencies are missing. Installing them now...")
        print("[!] This is only done once. Please wait a moment...\n")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            print("\n[+] Dependencies installed successfully!")
            
            import importlib
            importlib.invalidate_caches()
        except Exception as e:
            print(f"\n[X] CRITICAL ERROR: Auto-installation failed: {e}")
            print("[X] Please run 'pip install -r requirements.txt' manually in your terminal.")
            sys.exit(1)
    else:
        print("\n[X] CRITICAL ERROR: requirements.txt not found! 🥀")
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

last_response_time = 0
message_context_limit = 10
COMMAND_PREFIX = "!"

# For this to work you need to have the Vertex AI .json credetials file in this folder under the name "vertex-credentials.json"
# Here is a tutorial on how to get it https://docs.decisionrules.io/doc/ai-assistant/assistant-setup/google-vertex-credentials-json

load_dotenv()
# This is what you HAVE to have in the .env file:
#   GEMINI_API_KEY=your_api_key_here (optional)
#   DISCORD_TOKEN=your_discord_token_here
# You can get your API key from AI Studio: https://aistudio.google.com/api-keys (This will only be used when prompted to generate a Song)

CONFIG_FILE = "config.json"
# This is what you can add to the config.json file:
# {
#     "ALLOWED_CHANNELS": [], # If this is empty it will react to every message in every channel
#     "COOLDOWN_SECONDS": 5,
#     "BANNED_USERS": [],
#     "ALLOWED_IMAGE_USERS": [], # If this is empty it will not allow anyone, except you, to use the image command
#     "ALLOWED_VIDEO_USERS": [], # If this is empty it will not allow anyone, except you, to use the video command
#     "ALLOWED_SONG_USERS": [], # If this is empty it will not allow anyone, except you, to use the song command
#     "ACTIVE_MODEL": "gemini-2.5-flash", # The active text generation model for Vertex/Gemini
#     "ACTIVE_OLLAMA_MODEL": "llama3.2", # The active text generation model for local Ollama
#     "AI_BACKEND": "gemini", # Toggle between "gemini" and "ollama"
#     "FEATURES": {"IMAGE_ENABLED": True, "VIDEO_ENABLED": True, "SONG_ENABLED": True} # Global toggles
# }

def load_config():
    default_config = {
        "ALLOWED_CHANNELS": [],
        "COOLDOWN_SECONDS": 5,
        "BANNED_USERS": [],
        "ALLOWED_IMAGE_USERS": [],
        "ALLOWED_VIDEO_USERS": [],
        "ALLOWED_SONG_USERS": [],
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
            print(f"Created default {CONFIG_FILE}")
        except Exception as e:
            print(f"Failed to create config file: {e}")
        return default_config
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {CONFIG_FILE}: {e}. Using default config.")
        return default_config

config_data = load_config()

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")

if "ALLOWED_PAINT_USERS" in config_data:
    config_data["ALLOWED_IMAGE_USERS"] = config_data.pop("ALLOWED_PAINT_USERS")
    save_config()
if "FEATURES" not in config_data:
    config_data["FEATURES"] = {"IMAGE_ENABLED": True, "VIDEO_ENABLED": True, "SONG_ENABLED": True}
    save_config()
if "AI_BACKEND" not in config_data:
    config_data["AI_BACKEND"] = "gemini"
    save_config()
if "ACTIVE_OLLAMA_MODEL" not in config_data:
    config_data["ACTIVE_OLLAMA_MODEL"] = "llama3.2"
    save_config()

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "vertex-credentials.json")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE
VERTEX_PROJECT = "cloudstore-c1b65"
VERTEX_LOCATION = "us-central1"

gemini_client = None
try:
    gemini_client = genai.Client(
        vertexai=True,
        project=VERTEX_PROJECT,
        location=VERTEX_LOCATION
    )
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
        fallback_content = f"<@{message.author.id}>"
        if content:
            fallback_content += f" {content}"
        return await message.channel.send(content=fallback_content, **kwargs)
    except Exception as e:
        print(f"Unexpected error in safe_reply: {e}")
        return None

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

@bot.event
async def on_ready():
    print(f'Successfully logged in as {bot.user} (ID: {bot.user.id})')
    print('--------------------------------------------------')
    print(f'Prefix is set to: {COMMAND_PREFIX}')
    print(f'Use {COMMAND_PREFIX}self <prompt> to talk to the ai (the bot will ignore self pings)')
    print(f'Use {COMMAND_PREFIX}backend [gemini/ollama] to switch AI engines')
    print(f'Use {COMMAND_PREFIX}models list/set <model> to manage the active text model')
    print(f'Use {COMMAND_PREFIX}remember <user?> <text> to save a fact about a user or into global memories')
    print(f'Use {COMMAND_PREFIX}forget to delete every memory')
    print(f'Use {COMMAND_PREFIX}byebye to stop the bot')
    print(f'Use {COMMAND_PREFIX}refresh to refresh the bot')
    print(f'Use {COMMAND_PREFIX}image <prompt> to make a image')
    print(f'Use {COMMAND_PREFIX}video <prompt> to make a video')
    print(f'Use {COMMAND_PREFIX}song <prompt> to make a song')
    print(f'Use {COMMAND_PREFIX}user info <@user> to check a users permissions')
    print(f'Use {COMMAND_PREFIX}user ban/unban <@user> to manage bans')
    print(f'Use {COMMAND_PREFIX}user allow/deny <@user> [image/video/song] to manage feature access')
    print(f'Use {COMMAND_PREFIX}toggle [image/video/song] to enable/disable features globally')
    print('--------------------------------------------------')
    
    if os.path.exists("refresh_channel.txt"):
        try:
            with open("refresh_channel.txt", "r") as f:
                channel_id = int(f.read().strip())
            os.remove("refresh_channel.txt")
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

    if message.content.lower().startswith(f"{COMMAND_PREFIX}user info"):
        target = message.author
        if message.mentions and message.author.id == bot.user.id:
            target = message.mentions[0]
        
        is_banned = target.id in config_data.get("BANNED_USERS", [])
        can_img = target.id in config_data.get("ALLOWED_IMAGE_USERS", [])
        can_vid = target.id in config_data.get("ALLOWED_VIDEO_USERS", [])
        can_sng = target.id in config_data.get("ALLOWED_SONG_USERS", [])
        
        msg = f"**User Info for {target.name}** 👤\n"
        msg += f"**Banned:** {'Yes' if is_banned else 'No'}\n"
        msg += f"**Image Gen:** {'Allowed' if can_img else 'Denied'}\n"
        msg += f"**Video Gen:** {'Allowed' if can_vid else 'Denied'}\n"
        msg += f"**Song Gen:** {'Allowed' if can_sng else 'Denied'}"
        
        await safe_reply(message, content=msg, delete_after=5)
        return

    is_self_cmd = message.content.startswith(f"{COMMAND_PREFIX}self ")

    if message.author == bot.user and not is_self_cmd:
        await bot.process_commands(message)
        return

    allowed_channels = config_data.get("ALLOWED_CHANNELS", [])
    if allowed_channels and message.channel.id not in allowed_channels:
        return

    if message.content.startswith(f"{COMMAND_PREFIX}image ") and message.author.id in config_data.get("ALLOWED_IMAGE_USERS", []):
        if not features.get("IMAGE_ENABLED", True):
            await safe_reply(message, content="Cant create an image rn. 🛑")
            return
        prompt = message.content[len(f"{COMMAND_PREFIX}image "):].strip()
        if prompt:
            await process_image_request(message, prompt)
            return

    if message.content.startswith(f"{COMMAND_PREFIX}video ") and message.author.id in config_data.get("ALLOWED_VIDEO_USERS", []):
        if not features.get("VIDEO_ENABLED", True):
            await safe_reply(message, content="Cant create a video rn. 🛑")
            return
        prompt = message.content[len(f"{COMMAND_PREFIX}video "):].strip()
        if prompt:
            await process_video_request(message, prompt)
            return

    if message.content.startswith(f"{COMMAND_PREFIX}song ") and message.author.id in config_data.get("ALLOWED_SONG_USERS", []):
        if not features.get("SONG_ENABLED", True):
            await safe_reply(message, content="Cant create a song rn. 🛑")
            return
        prompt = message.content[len(f"{COMMAND_PREFIX}song "):].strip()
        if prompt:
            await process_song_request(message, prompt)
            return

    if bot.user not in message.mentions and not is_self_cmd:
        await bot.process_commands(message)
        return

    current_time = time.time()
    if current_time - last_response_time < config_data.get("COOLDOWN_SECONDS", 5):
        return
    
    if is_self_cmd:
        user_msg = message.content[len(f"{COMMAND_PREFIX}self "):].strip()
    else:
        user_msg = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        
    if not user_msg:
        return
        
    context = f"[METADATA]\n"
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
        if os.path.exists("instructions.txt"):
            with open("instructions.txt", "r", encoding="utf-8") as f:
                sys_instruct = f.read().strip()
        
        if os.path.exists("global_memory.txt"):
            with open("global_memory.txt", "r", encoding="utf-8") as f:
                memory_data = f.read().strip()
            if memory_data:
                sys_instruct += "\n\n[GLOBAL MEMORY]:\n" + memory_data

        user_id_str = str(message.author.id)
        if os.path.exists("user_memories.json"):
            try:
                with open("user_memories.json", "r", encoding="utf-8") as f:
                    all_users_mem = json.load(f)
                if user_id_str in all_users_mem and all_users_mem[user_id_str]:
                    sys_instruct += "\n\n[USER SPECIFIC MEMORY (" + message.author.name + ")]:\n"
                    for fact in all_users_mem[user_id_str]:
                        sys_instruct += f"- {fact}\n"
            except:
                pass

        sys_instruct += "\n\nIMPORTANT: You have long-term memory! Check the provided [GLOBAL MEMORY] and [USER SPECIFIC MEMORY] above. Do NOT store a fact if it is already there. Only store NEW and IMPORTANT information.\n"
        sys_instruct += "- For global facts: append [GLOBALMEM: fact to store].\n"
        sys_instruct += "- For facts about the current user: append [USERMEM: fact to store].\n"
        sys_instruct += "Only use these tags at the very end of your response."

        can_image = features.get("IMAGE_ENABLED", True) and message.author.id in config_data.get("ALLOWED_IMAGE_USERS", [])
        can_video = features.get("VIDEO_ENABLED", True) and message.author.id in config_data.get("ALLOWED_VIDEO_USERS", [])
        can_song = features.get("SONG_ENABLED", True) and message.author.id in config_data.get("ALLOWED_SONG_USERS", [])

        if can_image or can_video or can_song:
            sys_instruct += "\n\nAUTO-MEDIA GENERATION: You can generate media for the user! Only use these tags when EXPLICITLY requested by the user:\n"
            if can_image:
                sys_instruct += "- For images: [IMAGE: detailed image prompt in english]\n"
            if can_video:
                sys_instruct += "- For videos: [VIDEO: detailed video prompt in english]\n"
            if can_song:
                sys_instruct += "- For songs: [SONG: detailed song/music prompt in english]\n"
            sys_instruct += "Example: if user says 'male mir eine katze', respond normally and add [IMAGE: a cute fluffy cat sitting on a pillow] at the very end.\nOnly use ONE media tag per message."

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
            payload = {
                "model": active_ollama_model,
                "messages": messages,
                "stream": False
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(ollama_url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            reply_text = data.get("message", {}).get("content", "")
                        else:
                            reply_text = f"Ollama Error ({resp.status}): Make sure Ollama is running and model '{active_ollama_model}' is pulled."
            except aiohttp.ClientConnectorError:
                reply_text = "Connection refused: Ollama is not running on localhost:11434 🛑"
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

        global_mems = re.findall(r'\[GLOBALMEM:\s*(.*?)\]', reply_text)
        if global_mems:
            existing_global = []
            if os.path.exists("global_memory.txt"):
                try:
                    with open("global_memory.txt", "r", encoding="utf-8") as f:
                        existing_global = [line.strip().lstrip("- ").strip() for line in f.readlines()]
                except:
                    pass
            
            with open("global_memory.txt", "a", encoding="utf-8") as f:
                for mem in global_mems:
                    m_strip = mem.strip()
                    if m_strip and m_strip not in existing_global:
                        f.write(f"- {m_strip}\n")
                        existing_global.append(m_strip)
            reply_text = re.sub(r'\[GLOBALMEM:\s*.*?\]', '', reply_text).strip()

        user_mems = re.findall(r'\[USERMEM:\s*(.*?)\]', reply_text)
        if user_mems:
            user_id_str = str(message.author.id)
            all_users_mem = {}
            if os.path.exists("user_memories.json"):
                try:
                    with open("user_memories.json", "r", encoding="utf-8") as f:
                        all_users_mem = json.load(f)
                except:
                    pass
            
            if user_id_str not in all_users_mem:
                all_users_mem[user_id_str] = []
            
            for mem in user_mems:
                m_strip = mem.strip()
                if m_strip and m_strip not in all_users_mem[user_id_str]:
                    all_users_mem[user_id_str].append(m_strip)
            
            with open("user_memories.json", "w", encoding="utf-8") as f:
                json.dump(all_users_mem, f, indent=4)
                
            reply_text = re.sub(r'\[USERMEM:\s*.*?\]', '', reply_text).strip()
        
        image_match = re.search(r'\[IMAGE:\s*(.*?)\]', reply_text)
        if not image_match:
            image_match = re.search(r'\[PAINT:\s*(.*?)\]', reply_text)
            
        video_match = re.search(r'\[VIDEO:\s*(.*?)\]', reply_text)
        song_match = re.search(r'\[SONG:\s*(.*?)\]', reply_text)
        
        if image_match:
            reply_text = re.sub(r'\[(?:IMAGE|PAINT):\s*.*?\]', '', reply_text).strip()
        if video_match:
            reply_text = re.sub(r'\[VIDEO:\s*.*?\]', '', reply_text).strip()
        if song_match:
            reply_text = re.sub(r'\[SONG:\s*.*?\]', '', reply_text).strip()
            
    except Exception as e:
        reply_text = random.choice(ERROR_MSGS).format(e=e)
        image_match = None
        video_match = None
        song_match = None
        
    if reply_text:
        if len(reply_text) > 3900:
            file_obj = io.BytesIO(reply_text.encode('utf-8'))
            file = discord.File(file_obj, filename="ai_antwort.txt")
            await safe_reply(message, content="*Na what you wanted was lowkey too long 🥀*", file=file)
        else:
            await safe_reply(message, content=reply_text + AI_MARKER)
    
    if image_match and can_image:
        asyncio.create_task(process_image_request(message, image_match.group(1)))
    elif video_match and can_video:
        asyncio.create_task(process_video_request(message, video_match.group(1)))
    elif song_match and can_song:
        asyncio.create_task(process_song_request(message, song_match.group(1)))

# ---------------------------------------------------------
# MEDIA PROCESSORS
# ---------------------------------------------------------

async def process_image_request(message, prompt: str):
    if not gemini_client:
        print("No Gemini API Key found")
        return

    try:
        msg = await safe_reply(message, content=random.choice(IMAGE_START_MSGS))
        
        result = await gemini_client.aio.models.generate_images(
            model='imagen-4.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
            )
        )
        
        if result.generated_images is None:
            if msg: await msg.edit(content="Nah fam, API didn't return an image (prompt might be blocked 💀)." + AI_MARKER)
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
        op = await gemini_client.aio.models.generate_videos(
            model='veo-2.0-generate-001',
            prompt=prompt
        )
        
        while not op.done:
            await asyncio.sleep(5)
            op = await gemini_client.aio.operations.get(operation=op)
            
        if op.error:
            if msg: await msg.edit(content=f"Nah fam, API threw an error: {op.error.message}" + AI_MARKER)
            return
            
        final_result = getattr(op, 'result', getattr(op, 'response', None))
        
        if final_result and final_result.generated_videos:
            for generated_video in final_result.generated_videos:
                video_data = generated_video.video.video_bytes

                if (video_data is None or len(video_data) == 0) and getattr(generated_video.video, 'uri', None):
                    if msg: await msg.edit(content=random.choice(VIDEO_LARGE_MSGS) + AI_MARKER)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(generated_video.video.uri) as resp:
                            if resp.status == 200:
                                video_data = await resp.read()
                            else:
                                if msg: await msg.edit(content=f"Ah nah fam, error downloading Video. URI Status: {resp.status}" + AI_MARKER)
                                return
                
                if not video_data or len(video_data) == 0:
                    if msg: await msg.edit(content="API returned an empty video object and no valid URI. (Prompt blocked or error) 💀" + AI_MARKER)
                    return
                
                file_obj = io.BytesIO(video_data)
                file = discord.File(file_obj, filename="video.mp4")
                try:
                    await safe_reply(message, content=random.choice(VIDEO_DONE_MSGS), file=file)
                except Exception as e:
                    cloud_uri = getattr(generated_video.video, 'uri', 'Nicht verfügbar')
                    await safe_reply(message, content=f"Bro the video is too big 😭 ({len(video_data)/(1024*1024):.2f}MB).\nDownload it or smth: {cloud_uri}")
                break
        else:
             if msg: await msg.edit(content="Nah fam, API didn't return any video (prompt might be blocked 💀)." + AI_MARKER)
             
        try:
            if msg: await msg.delete()
        except:
            pass
            
    except Exception as e:
        await safe_reply(message, content=random.choice(ERROR_MSGS).format(e=e))

async def process_song_request(message, prompt: str):
    if not lyria_client:
        await safe_reply(message, content="Cant make songs rn gng 🥀, I need your ai studio API Key 🤑.")
        return

    msg = await safe_reply(message, content=random.choice(SONG_START_MSGS))
    try:
        response = await lyria_client.aio.models.generate_content(
            model='lyria-3-clip-preview',
            contents=prompt,
        )
        
        audio_data = None
        lyrics_parts = []
        for part in response.parts:
            if part.text is not None:
                lyrics_parts.append(part.text)
            elif part.inline_data is not None:
                audio_data = part.inline_data.data
        
        if not audio_data:
            if msg: await msg.edit(content="Nah fam, API didn't return any audio (prompt might be blocked 💀)." + AI_MARKER)
            return
            
        file_obj = io.BytesIO(audio_data)
        file = discord.File(file_obj, filename="song.mp3")
        
        lyrics_text = ""
        if lyrics_parts:
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

# ---------------------------------------------------------
# BOT COMMANDS
# ---------------------------------------------------------

async def handle_list_toggle(ctx, list_key: str, action_name: str, add: bool):
    try:
        await ctx.message.delete()
    except:
        pass

    if not ctx.message.mentions:
        await ctx.send(f"You gotta ping someone 💀" + AI_MARKER, delete_after=5)
        return

    user_id = ctx.message.mentions[0].id
    user_name = ctx.message.mentions[0].name
    
    current_list = config_data.get(list_key, [])
    
    if add:
        if user_id not in current_list:
            current_list.append(user_id)
            config_data[list_key] = current_list
            save_config()
            await ctx.send(f"Successfully {action_name} {user_name} 📝" + AI_MARKER, delete_after=3)
        else:
            await ctx.send(f"{user_name} is already {action_name} 💀" + AI_MARKER, delete_after=3)
    else:
        if user_id in current_list:
            current_list.remove(user_id)
            config_data[list_key] = current_list
            save_config()
            await ctx.send(f"Successfully removed {user_name} from {action_name} 📝" + AI_MARKER, delete_after=3)
        else:
            await ctx.send(f"{user_name} is not {action_name} 💀" + AI_MARKER, delete_after=3)

@bot.group(invoke_without_command=True)
async def user(ctx):
    try: await ctx.message.delete()
    except: pass
    await ctx.send(f"Usage:\n`{COMMAND_PREFIX}user info [@user]`\n`{COMMAND_PREFIX}user ban/unban <@user>`\n`{COMMAND_PREFIX}user allow/deny <@user> <image/video/song>`" + AI_MARKER, delete_after=10)

@user.command()
async def ban(ctx):
    await handle_list_toggle(ctx, "BANNED_USERS", "banned", add=True)

@user.command()
async def unban(ctx):
    await handle_list_toggle(ctx, "BANNED_USERS", "banned", add=False)

@user.command()
async def allow(ctx, perm_type: str = None):
    if not perm_type or perm_type.lower() not in ["image", "video", "song"]:
        await ctx.send(f"Specify what to allow: `image`, `video`, or `song`" + AI_MARKER, delete_after=5)
        return
    list_key = f"ALLOWED_{perm_type.upper()}_USERS"
    await handle_list_toggle(ctx, list_key, f"allowed to use {perm_type.lower()}", add=True)

@user.command()
async def deny(ctx, perm_type: str = None):
    if not perm_type or perm_type.lower() not in ["image", "video", "song"]:
        await ctx.send(f"Specify what to deny: `image`, `video`, or `song`" + AI_MARKER, delete_after=5)
        return
    list_key = f"ALLOWED_{perm_type.upper()}_USERS"
    await handle_list_toggle(ctx, list_key, f"allowed to use {perm_type.lower()}", add=False)


@bot.command()
async def toggle(ctx, feature: str = None):
    try: await ctx.message.delete()
    except: pass
    
    valid_features = ["image", "video", "song"]
    if not feature or feature.lower() not in valid_features:
        await ctx.send(f"Specify what to toggle: `image`, `video`, or `song`" + AI_MARKER, delete_after=5)
        return
        
    feat_key = f"{feature.upper()}_ENABLED"
    features = config_data.setdefault("FEATURES", {})
    
    current_state = features.get(feat_key, True)
    new_state = not current_state
    
    features[feat_key] = new_state
    save_config()
    
    state_str = "ENABLED ✅" if new_state else "DISABLED 🛑"
    await ctx.send(f"Global feature `{feature}` is now {state_str}" + AI_MARKER, delete_after=5)

@bot.command()
async def backend(ctx, backend_name: str = None):
    try: await ctx.message.delete()
    except: pass
    
    valid = ["gemini", "ollama"]
    if not backend_name or backend_name.lower() not in valid:
        current = config_data.get("AI_BACKEND", "gemini")
        await ctx.send(f"Current Backend: `{current}`\nUsage: `{COMMAND_PREFIX}backend [gemini|ollama]`" + AI_MARKER, delete_after=8)
        return
        
    config_data["AI_BACKEND"] = backend_name.lower()
    save_config()
    await ctx.send(f"AI Backend switched to `{backend_name.lower()}` 🔄" + AI_MARKER, delete_after=5)

@bot.command()
async def models(ctx, action: str = None, model_name: str = None):
    try:
        await ctx.message.delete()
    except:
        pass

    backend = config_data.get("AI_BACKEND", "gemini")

    if action == "list":
        if backend == "gemini":
            active = config_data.get("ACTIVE_MODEL", "gemini-2.5-flash")
            try:
                api_models = await gemini_client.aio.models.list()
                names = sorted(list(set([m.name.split('/')[-1] for m in api_models if "gemini" in m.name.lower()])))
                
                msg = "**Available Models from Vertex (Gemini):**\n"
                for m in names:
                    marker = " (Active)" if m == active else ""
                    msg += f"- `{m}`{marker}\n"
                await ctx.send(msg + AI_MARKER, delete_after=15)
            except Exception as e:
                await ctx.send(f"Error fetching Vertex models: {e}" + AI_MARKER, delete_after=5)
                
        elif backend == "ollama":
            active = config_data.get("ACTIVE_OLLAMA_MODEL", "llama3.2")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:11434/api/tags") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            names = [m["name"] for m in data.get("models", [])]
                            
                            msg = "**Available Local Models (Ollama):**\n"
                            for m in names:
                                marker = " (Active)" if m == active else ""
                                msg += f"- `{m}`{marker}\n"
                            await ctx.send(msg + AI_MARKER, delete_after=15)
                        else:
                            await ctx.send("Ollama is not responding or not running locally 🛑" + AI_MARKER, delete_after=5)
            except Exception as e:
                await ctx.send(f"Failed to connect to local Ollama API: {e}" + AI_MARKER, delete_after=5)
        
    elif action == "set":
        if not model_name:
            await ctx.send(f"You gotta specify a model name! Like: `{COMMAND_PREFIX}models set llama3`" + AI_MARKER, delete_after=5)
            return
            
        if backend == "gemini":
            config_data["ACTIVE_MODEL"] = model_name
        else:
            config_data["ACTIVE_OLLAMA_MODEL"] = model_name
            
        save_config()
        await ctx.send(f"Active {backend} model set to `{model_name}`" + AI_MARKER, delete_after=5)
        
    else:
        await ctx.send(f"Usage:\n`{COMMAND_PREFIX}models list` -> Shows models for current backend\n`{COMMAND_PREFIX}models set <model>` -> Changes active model" + AI_MARKER, delete_after=8)

@bot.command()
async def song(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send(f"Blud, I cant create a song out of nthn 🥀, use it like this: `{COMMAND_PREFIX}song [prompt]`" + AI_MARKER, delete_after=5)
        return
    await process_song_request(ctx.message, prompt)

@bot.command()
async def video(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send(f"Blud, I cant create a video out of nthn 🥀, use it like this: `{COMMAND_PREFIX}video [prompt]`" + AI_MARKER, delete_after=5)
        return
    await process_video_request(ctx.message, prompt)

@bot.command()
async def image(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send(f"Blud, I cant create a image out of nthn 🥀, use it like this: `{COMMAND_PREFIX}image [prompt]`" + AI_MARKER, delete_after=5)
        return
    await process_image_request(ctx.message, prompt)

@bot.command()
async def remember(ctx, *, text: str):
    try:
        await ctx.message.delete()
    except:
        pass
        
    mentions = ctx.message.mentions
    if mentions:
        target_user = mentions[0]
        fact = text.replace(f'<@{target_user.id}>', '').replace(f'<@!{target_user.id}>', '').strip()
        
        user_memories = {}
        if os.path.exists("user_memories.json"):
            try:
                with open("user_memories.json", "r", encoding="utf-8") as f:
                    user_memories = json.load(f)
            except:
                pass
                
        target_id_str = str(target_user.id)
        if target_id_str not in user_memories:
            user_memories[target_id_str] = []
            
        if fact and fact not in user_memories[target_id_str]:
            user_memories[target_id_str].append(fact)
        
        with open("user_memories.json", "w", encoding="utf-8") as f:
            json.dump(user_memories, f, indent=4)
            
        try:
            await ctx.send(f"K gng ill remember dat for {target_user.name} 📝" + AI_MARKER, delete_after=3)
        except:
            pass
    else:
        existing_global = []
        if os.path.exists("global_memory.txt"):
            try:
                with open("global_memory.txt", "r", encoding="utf-8") as f:
                    existing_global = [line.strip().lstrip("- ").strip() for line in f.readlines()]
            except:
                pass
        
        if text.strip() not in existing_global:
            with open("global_memory.txt", "a", encoding="utf-8") as f:
                f.write(f"- {text.strip()}\n")
        try:
            await ctx.send(f"K gng ill remember dat globally 🌎" + AI_MARKER, delete_after=3)
        except:
            pass

@bot.command()
async def forget(ctx):
    if os.path.exists("global_memory.txt"):
        os.remove("global_memory.txt")
    if os.path.exists("user_memories.json"):
        os.remove("user_memories.json")
    try:
        await ctx.message.delete()
        await ctx.send("Say bye to your info 🤑" + AI_MARKER, delete_after=2)
    except:
        pass

@bot.command()
async def byebye(ctx):
    print("Stop bot by using !byebye")
    try:
        await ctx.message.delete()
        await ctx.send("Bye gng" + AI_MARKER, delete_after=2)
    except:
        pass
    await bot.close()

@bot.command()
async def refresh(ctx):
    with open("refresh_channel.txt", "w") as f:
        f.write(str(ctx.channel.id))
    try:
        await ctx.message.delete()
        await ctx.send("brb" + AI_MARKER, delete_after=3)
    except:
        pass
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.command()
async def purge(ctx, amount: int = 10, scope: str = "channel"):
    try:
        await ctx.message.delete()
    except:
        pass
    
    deleted = 0
    limit_scan = 1000 
    
    allowed_channels = config_data.get("ALLOWED_CHANNELS", [])
    
    if scope == "all" and allowed_channels:
        for ch_id in allowed_channels:
            channel = bot.get_channel(ch_id)
            if channel:
                try:
                    async for msg in channel.history(limit=limit_scan):
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
                
        try:
            await ctx.send(f"Byebye to {deleted} messages 🤑" + AI_MARKER, delete_after=3)
        except:
            pass
            
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
            await ctx.send(f"Byebye to {deleted} messages 🤑" + AI_MARKER, delete_after=3)
        except:
            pass

# --- EXECUTION ---
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    
    if not TOKEN:
        print("Error: No DISCORD_TOKEN found in .env file.")
    else:
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            print("Error: Invalid Token passed. Please check your User Token.")
        except Exception as e:
            print(f"An error occurred: {e}")