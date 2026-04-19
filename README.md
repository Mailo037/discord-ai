# Discord AI Assistant (Self-Bot)

A highly autonomous, multimodal Discord AI assistant powered by Google Vertex AI (Gemini) and Ollama.

## Features

- **Dual-Layer Memory**: Remembers facts about individual users and global context.
- **AI Media Generation**: Create high-quality Images, Videos, and Songs directly in Discord.
- **Multi-Backend Support**: Toggle between Google Gemini (Cloud) and Ollama (Local) on the fly.
- **Advanced Moderation**: Manage user permissions, bans, and feature access.
- **Auto-Setup**: Automatically installs all missing dependencies on startup.
- **Cross-Platform**: Works out-of-the-box on Windows and Linux.

---

## Quick Start

### 1. Prerequisites
- **Python 3.8+** installed.
- **Discord Token**: Your account token (This is a self-bot).
- **Google Cloud Project**: A Vertex AI enabled project and a `vertex-credentials.json` file in the project root.
- **Ollama (Optional)**: If you want to use local models.

### 2. Configuration
Create a `.env` file in the root directory:
```env
DISCORD_TOKEN=your_token_here
GEMINI_API_KEY=your_google_api_key_here
```

### 3. Installation & Running

#### **Windows**
Simply double-click **`install.bat`**. It will install everything and start the bot.

#### **Linux**
Run the following commands:
```bash
chmod +x install.sh
./install.sh
```

---

## Commands

| Command | Description |
| :--- | :--- |
| `!self <prompt>` | Talk directly to the AI. |
| `!backend <type>` | Switch between `gemini` and `ollama`. |
| `!models list/set` | Manage active text models. |
| `!image <prompt>` | Generate an AI image. |
| `!video <prompt>` | Generate an AI video (takes a few minutes). |
| `!song <prompt>` | Generate an AI song with lyrics. |
| `!user info <@user>` | Check a user's permissions and status. |
| `!user ban/unban` | Manage access to the bot. |
| `!user allow/deny` | Grant or revoke access to media generation. |
| `!toggle <feature>` | Enable/Disable features (`image`, `video`, `song`) globally. |
| `!remember <text>` | Manually save a fact to memory. |
| `!forget` | Wipe all global and user memories. |
| `!refresh` | Restart the bot to apply changes. |
| `!byebye` | Stop the bot. |

---

## Project Structure
- `bot.py`: The main bot logic.
- `config.json`: Persistent settings (Roles, Banned Users, Feature Toggles).
- `requirements.txt`: Python dependency list.
- `user_memories.json`: Database for user-specific facts.
- `global_memory.txt`: Database for global context.
- `instructions.txt`: Custom system instructions for the AI behavior.

## Disclaimer
This is a self-bot. Using self-bots can be against Discord's Terms of Service. Use at your own risk.
