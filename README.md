# Discord AI Assistant (Self-Bot)

A premium, highly autonomous, multimodal Discord AI assistant powered by **Google Vertex AI (Gemini)** and **Ollama**. Features advanced memory systems, autonomous media generation, per-user personalities, and a robust permission configuration.

---

## Key Features

- **Dual-Layer Memory** — Tracks global facts and individual user history across conversations.
- **Autonomous Media Generation** — AI can proactively generate Images (Imagen 4.0), Videos (Veo 2.0), and Songs (Lyria) from text prompts.
- **User Personalities** — Authorized users can set a custom AI personality in DMs.
- **Multi-Backend Support** — Seamlessly switch between Google Gemini (Cloud) and Ollama (Local).
- **Silent Mode (`!s`)** — Run commands without any Discord output; side effects still apply.
- **Console Mode (`!c`)** — Redirect command output to the terminal instead of Discord.
- **Granular Permissions** — Per-user control over image, video, song, and personality features.
- **Auto-Installer** — Missing dependencies are installed automatically on startup.
- **Advanced Cooldowns** — Global cooldowns with per-channel overrides.

---

## Quick Start

### Prerequisites
- **Python 3.8+**
- **Google Cloud Project** with Vertex AI enabled — place `vertex-credentials.json` in the root folder ([setup guide](https://docs.decisionrules.io/doc/ai-assistant/assistant-setup/google-vertex-credentials-json))
- **Ollama** (optional) for local inference

### Configuration

Create a `.env` file in the root folder:

```env
DISCORD_TOKEN=your_token_here
GEMINI_API_KEY=your_google_api_key_here  # Optional: only needed for Lyria song generation
```

### Running

- **Windows:** Run `install.bat`
- **Linux:** `chmod +x install.sh && ./install.sh`

---

## Command Modifiers

Two special prefix characters can be prepended to supported commands:

### `!s` — Silent Mode

Executes the command with **no Discord output**. Side effects (config changes, memory saves, etc.) still happen normally. The command message itself is still deleted as usual.

```
!sremember @user likes cats     → saves memory, no confirmation message
!sbackend ollama                → switches backend silently
!stoggle image                  → toggles image feature silently
!suser allow @user image        → grants permission silently
!schannel add                   → whitelists channel silently
```

**Supported:** `image`, `song`, `remember`, `backend`, `toggle`, `user`, `channel`, `models`, `personality`, `purge`

> ⚠️ **`!video` does not support silent mode** — rendering takes several minutes and requires progress feedback.

---

### `!c` — Console Mode

Sends command output to the **terminal/console** instead of posting it in Discord. Useful for checking status or reading memories without cluttering the chat.

```
!cstatus              → prints full status block to terminal
!cmemories all        → dumps all memories to terminal
!cmodels list         → lists available models in terminal
!cuser info @user     → prints user permissions to terminal
!cchannel status      → prints channel info to terminal
```

**Supported:** `status`, `memories`, `models`, `user`, `channel`

---

## Commands

### AI Interaction

| Command | Description |
| :--- | :--- |
| `!self <prompt>` | Talk directly to the AI (ignores self-pings). |
| `!backend <gemini/ollama>` | Switch the AI text generation engine. |
| `!models list/set <model>` | List or set the active text model. |
| `!status` | Show system uptime and service connection status. |

### Media Generation

| Command | Description |
| :--- | :--- |
| `!image <prompt>` | Generate a high-quality AI image. Supports `!s`. |
| `!video <prompt>` | Create an AI video — takes a few minutes to render. **No silent/console.** |
| `!song <prompt>` | Produce an AI song with lyrics and audio. Supports `!s`. |
| `!toggle <feature>` | Globally enable/disable `image`, `video`, or `song`. Supports `!s`. |

### Memory & Personalities

| Command | Description |
| :--- | :--- |
| `!remember <text>` | Manually add a global memory. Supports `!s`. |
| `!remember @user <text>` | Manually add a memory for a specific user. Supports `!s`. |
| `!memories all` | List all global and user memories. Supports `!c`. |
| `!memories global` | Show global memories. Supports `!c`. |
| `!memories user [@user]` | Show memories for a user. Supports `!c`. |
| `!memories delete ...` | Selective deletion — see `!memories` for subcommands. |
| `!personality <text>` | Set your custom AI personality (DMs only, requires permission). Supports `!s`. |
| `!personality view [@user]` | View your own or another user's personality. |
| `!personality clear` | Remove your custom personality. Supports `!s`. |

### Administration

| Command | Description |
| :--- | :--- |
| `!user info <@user>` | View permissions and status for a user. Supports `!c`. |
| `!user allow/deny <@user> <perm>` | Manage permissions: `image`, `video`, `song`, `personality`. Supports `!s`. |
| `!user ban/unban <@user>` | Restrict or restore bot access. Supports `!s`. |
| `!channel add/remove [id]` | Manage allowed channels. Supports `!s`. |
| `!channel status [id]` | Check if a channel is whitelisted. Supports `!c`. |
| `!channel cooldown <s/off> [id]` | Set or remove a per-channel cooldown. Supports `!s`. |
| `!purge [amount] [channel/all]` | Delete bot messages. Supports `!s`. |
| `!refresh` | Restart the bot process. |
| `!byebye` | Shut down the bot. |

---

## AI Autonomous Tags

The AI manages its own state using special tags appended to its responses. You can also use these tags directly in your prompts.

### Memory

| Tag | Action |
| :--- | :--- |
| `[GLOBALMEM: <fact>]` | Save a fact visible to everyone. |
| `[USERMEM: <fact>]` | Save a fact about the current user. |
| `[DELMEM: <text>]` | Delete a matching user-specific memory. |
| `[DELGLOBALMEM: <text>]` | Delete a matching global memory. |

### Media

| Tag | Action |
| :--- | :--- |
| `[IMAGE: <prompt>]` | Trigger image generation. |
| `[VIDEO: <prompt>]` | Trigger video generation. |
| `[SONG: <prompt>]` | Trigger song generation. |

---

## Project Structure

| File | Purpose |
| :--- | :--- |
| `bot.py` | Core application logic and event handling. |
| `config.json` | Persistent settings, permissions, and channel lists. |
| `instructions.txt` | System instructions that shape the AI's personality and behavior. |
| `vertex-credentials.json` | Google Cloud service account credentials. |
| `user_personalities.json` | Storage for custom user-defined AI behaviors. |
| `user_memories.json` | Per-user long-term memory database. |
| `global_memory.txt` | Global long-term memory shared across all users. |

---

> [!CAUTION]
> This is a self-bot. Using self-bots is against Discord's Terms of Service. **Use at your own risk.**