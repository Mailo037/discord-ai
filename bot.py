import discord
from discord.ext import commands
import io
import re
import os
import time
import sys
import asyncio
import json
import aiohttp
import random
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
#   GEMINI_API_KEY=your_api_key_here
#   DISCORD_TOKEN=your_discord_token_here
# You can get your API key from AI Studio: https://aistudio.google.com/api-keys (This will only be used when prompted to generate an Song)

CONFIG_FILE = "config.json"
# This is what you can add to the config.json file:
# {
#     "ALLOWED_CHANNELS": [], # If this is empty it will react to every message in every channel
#     "COOLDOWN_SECONDS": 5,
#     "BANNED_USERS": [],
#     "ALLOWED_PAINT_USERS": [], # If this is empty it will not allow anyone, except you, to use the paint command
#     "ALLOWED_VIDEO_USERS": [], # If this is empty it will not allow anyone, except you, to use the video command
#     "ALLOWED_SONG_USERS": [] # If this is empty it will not allow anyone, except you, to use the song command
# }

def load_config():
    default_config = {
        "ALLOWED_CHANNELS": [],
        "COOLDOWN_SECONDS": 5,
        "BANNED_USERS": [],
        "ALLOWED_PAINT_USERS": [],
        "ALLOWED_VIDEO_USERS": [],
        "ALLOWED_SONG_USERS": []
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

ALLOWED_CHANNELS = config_data.get("ALLOWED_CHANNELS", [])
COOLDOWN_SECONDS = config_data.get("COOLDOWN_SECONDS", 5)
BANNED_USERS = config_data.get("BANNED_USERS", [])
ALLOWED_PAINT_USERS = config_data.get("ALLOWED_PAINT_USERS", [])
ALLOWED_VIDEO_USERS = config_data.get("ALLOWED_VIDEO_USERS", [])
ALLOWED_SONG_USERS = config_data.get("ALLOWED_SONG_USERS", [])

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

bot = commands.Bot(command_prefix="!", self_bot=True)

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

PAINT_START_MSGS = ["Lemme paint ts 😭🙏", "Hold on, cooking up a masterpiece 👨‍🎨", "Generating your image blud... ⏳", "Gotchu, drawing this rn 🖌️"]
PAINT_DONE_MSGS = ["Heres yo image blud 🤑", "Ts goes hard ngl 🔥", "Done painting this for u 🎨", "Masterpiece completed 🖼️"]

VIDEO_START_MSGS = ["Lemme cook up this video ts 🎬 (this takes some minutes)", "Directing your movie rn 🎥 (gimme a few mins)", "Generating video... grab some popcorn 🍿", "Cooking up the visuals, hold tight 🎞️"]
VIDEO_DONE_MSGS = ["Here is your video blud 🎥", "Movie is ready, ts is crazy 🎬", "Done rendering your clip 🎞️", "Here you go, Spielberg 🍿"]
VIDEO_LARGE_MSGS = ["Video generated but it is large. Downloading from Cloud URI... ⏳", "File is massive, pulling it from the cloud rn ☁️", "Hold on, downloading the big file... 📡"]

SONG_START_MSGS = ["Lemme cook up this song 🎵 (hold on)", "Producing your track rn 🎧 (wait a sec)", "Making beats for you... 🎹", "Tuning the instruments, gimme a sec 🎸"]
SONG_DONE_MSGS = ["Here is your song blud 🎶", "Track is ready, ts is a banger 🎧", "Done producing your audio 🔊", "Grammy winning track right here 🏆"]

ERROR_MSGS = ["Nah fam, ts was too hard: {e}", "Bro broke the API: {e} 💀", "My bad gng, error: {e} 🥀", "Aint no way, something failed: {e} 📉"]

@bot.event
async def on_ready():
    print(f'Successfully logged in as {bot.user} (ID: {bot.user.id})')
    print('--------------------------------------------------')
    print(f'Prefix is set to: {COMMAND_PREFIX}')
    print(f'Use {COMMAND_PREFIX}self <prompt> to talk to the ai (the bot will ignore self pings)')
    print(f'Use {COMMAND_PREFIX}remember <user?> <text> to save a fact about a user or into global memories')
    print(f'Use {COMMAND_PREFIX}forget to delete every memory')
    print(f'Use {COMMAND_PREFIX}byebye to stop the bot')
    print(f'Use {COMMAND_PREFIX}refresh to refresh the bot')
    print(f'Use {COMMAND_PREFIX}paint <prompt> to make a image')
    print(f'Use {COMMAND_PREFIX}video <prompt> to make a video')
    print(f'Use {COMMAND_PREFIX}song <prompt> to make a song')
    print(f'Use {COMMAND_PREFIX}ban/unban <user> to ban/unban a user')
    print(f'Use {COMMAND_PREFIX}addpaint/rmpaint <user> to add/remove a user from the allowed paint list')
    print(f'Use {COMMAND_PREFIX}addvideo/rmvideo <user> to add/remove a user from the allowed video list')
    print(f'Use {COMMAND_PREFIX}addsong/rmsong <user> to add/remove a user from the allowed song list')
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

    is_self_cmd = message.content.startswith(f"{COMMAND_PREFIX}self ")

    if message.author == bot.user and not is_self_cmd:
        await bot.process_commands(message)
        return

    allowed_channels = config_data.get("ALLOWED_CHANNELS", [])
    if allowed_channels and message.channel.id not in allowed_channels:
        return

    if message.content.startswith(f"{COMMAND_PREFIX}paint ") and message.author.id in config_data.get("ALLOWED_PAINT_USERS", []):
        prompt = message.content[len(f"{COMMAND_PREFIX}paint "):].strip()
        if prompt:
            await process_paint_request(message, prompt)
            return

    if message.content.startswith(f"{COMMAND_PREFIX}video ") and message.author.id in config_data.get("ALLOWED_VIDEO_USERS", []):
        prompt = message.content[len(f"{COMMAND_PREFIX}video "):].strip()
        if prompt:
            await process_video_request(message, prompt)
            return

    if message.content.startswith(f"{COMMAND_PREFIX}song ") and message.author.id in config_data.get("ALLOWED_SONG_USERS", []):
        prompt = message.content[len(f"{COMMAND_PREFIX}song "):].strip()
        if prompt:
            await process_song_request(message, prompt)
            return

    if bot.user not in message.mentions:
        await bot.process_commands(message)
        return

    current_time = time.time()
    if current_time - last_response_time < config_data.get("COOLDOWN_SECONDS", 5):
        return
    
    if gemini_client:
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
                if clean_content.strip():
                    chat_history += f"{author_name}: {clean_content}\n"
        except:
            pass
        
        if chat_history:
            context += f"[RECENT CHAT HISTORY]\n{chat_history}\n"
        
        prompt = f"{context}[CURRENT MESSAGE]\n{user_msg}"
        
        last_response_time = current_time
            
        try:
            contents_list = []
            
            avatar_bytes = None
            avatar_mime = "image/png"
            if message.author.avatar:
                avatar_bytes = await message.author.avatar.read()
                avatar_mime = "image/gif" if message.author.avatar.is_animated() else "image/png"
            elif message.author.default_avatar:
                avatar_bytes = await message.author.default_avatar.read()
            
            if avatar_bytes:
                contents_list.append(types.Part.from_bytes(data=avatar_bytes, mime_type=avatar_mime))
                
            for attachment in message.attachments:
                if attachment.content_type and ("image" in attachment.content_type or "video" in attachment.content_type):
                    try:
                        att_bytes = await attachment.read()
                        contents_list.append(types.Part.from_bytes(data=att_bytes, mime_type=attachment.content_type))
                    except:
                        pass
            
            contents_list.append(prompt)
            
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

            sys_instruct += "\n\nAUTO-MEDIA GENERATION: You can generate media for the user! If the user asks you to create/generate/make an image, a video, or a song/music, append the corresponding tag at the VERY END of your answer (after any MEM tags). Only use these when the user EXPLICITLY asks for media creation:\n- For images: [PAINT: detailed image prompt in english]\n- For videos: [VIDEO: detailed video prompt in english]\n- For songs: [SONG: detailed song/music prompt in english]\nExample: if user says 'male mir eine katze', respond normally and add [PAINT: a cute fluffy cat sitting on a pillow]\nDo NOT use these tags unless the user clearly wants you to generate media. Only use ONE media tag per message."

            config_kwargs = {}
            if sys_instruct:
                config_kwargs['config'] = types.GenerateContentConfig(system_instruction=sys_instruct)

            response = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
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
            
            paint_match = re.search(r'\[PAINT:\s*(.*?)\]', reply_text)
            video_match = re.search(r'\[VIDEO:\s*(.*?)\]', reply_text)
            song_match = re.search(r'\[SONG:\s*(.*?)\]', reply_text)
            
            if paint_match:
                reply_text = re.sub(r'\[PAINT:\s*.*?\]', '', reply_text).strip()
            if video_match:
                reply_text = re.sub(r'\[VIDEO:\s*.*?\]', '', reply_text).strip()
            if song_match:
                reply_text = re.sub(r'\[SONG:\s*.*?\]', '', reply_text).strip()
                
        except Exception as e:
            reply_text = random.choice(ERROR_MSGS).format(e=e)
            paint_match = None
            video_match = None
            song_match = None
            
    else:
        print("No Vertex AI Client found")
        return
    
    if reply_text:
        if len(reply_text) > 3900:
            file_obj = io.BytesIO(reply_text.encode('utf-8'))
            file = discord.File(file_obj, filename="ai_antwort.txt")
            await safe_reply(message, content="*Na what you wanted was lowkey too long 🥀*", file=file)
        else:
            await safe_reply(message, content=reply_text + AI_MARKER)
    
    if paint_match and message.author.id in config_data.get("ALLOWED_PAINT_USERS", []):
        asyncio.create_task(process_paint_request(message, paint_match.group(1)))
    elif video_match and message.author.id in config_data.get("ALLOWED_VIDEO_USERS", []):
        asyncio.create_task(process_video_request(message, video_match.group(1)))
    elif song_match and message.author.id in config_data.get("ALLOWED_SONG_USERS", []):
        asyncio.create_task(process_song_request(message, song_match.group(1)))

# ---------------------------------------------------------
# MEDIA PROCESSORS
# ---------------------------------------------------------

async def process_paint_request(message, prompt: str):
    if not gemini_client:
        print("No Gemini API Key found")
        return

    try:
        msg = await safe_reply(message, content=random.choice(PAINT_START_MSGS))
        
        result = await gemini_client.aio.models.generate_images(
            model='imagen-4.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
            )
        )
        
        if result.generated_images is None:
            if msg: await msg.edit(content="Nah fam, API didn't return an image (prompt might be blocked 💀).")
            return
            
        for generated_image in result.generated_images:
            file_obj = io.BytesIO(generated_image.image.image_bytes)
            file = discord.File(file_obj, filename="bild.jpeg")
            await safe_reply(message, content=random.choice(PAINT_DONE_MSGS), file=file)
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
             if msg: await msg.edit(content="Nah fam, API didn't return any video (prompt might be blocked 💀).")
             
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
# BOT COMMANDS (CONFIG MANAGEMENT & OTHERS)
# ---------------------------------------------------------

async def handle_list_toggle(ctx, list_key: str, action_name: str, add: bool):
    """Helper command to add or remove users from config lists safely."""
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

@bot.command()
async def ban(ctx):
    await handle_list_toggle(ctx, "BANNED_USERS", "banned", add=True)

@bot.command()
async def unban(ctx):
    await handle_list_toggle(ctx, "BANNED_USERS", "banned", add=False)

@bot.command()
async def addpaint(ctx):
    await handle_list_toggle(ctx, "ALLOWED_PAINT_USERS", "allowed to paint", add=True)

@bot.command()
async def rmpaint(ctx):
    await handle_list_toggle(ctx, "ALLOWED_PAINT_USERS", "allowed to paint", add=False)

@bot.command()
async def addvideo(ctx):
    await handle_list_toggle(ctx, "ALLOWED_VIDEO_USERS", "allowed to video", add=True)

@bot.command()
async def rmvideo(ctx):
    await handle_list_toggle(ctx, "ALLOWED_VIDEO_USERS", "allowed to video", add=False)

@bot.command()
async def addsong(ctx):
    await handle_list_toggle(ctx, "ALLOWED_SONG_USERS", "allowed to song", add=True)

@bot.command()
async def rmsong(ctx):
    await handle_list_toggle(ctx, "ALLOWED_SONG_USERS", "allowed to song", add=False)


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
async def paint(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send(f"Blud, I cant create a image out of nthn 🥀, use it like this: `{COMMAND_PREFIX}paint [prompt]`" + AI_MARKER, delete_after=5)
        return
    await process_paint_request(ctx.message, prompt)

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
    os.execv(sys.executable, ['python'] + sys.argv)

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