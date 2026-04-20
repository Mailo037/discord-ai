# Discord AI Assistant (Self-Bot)

A premium, highly autonomous, multimodal Discord AI assistant powered by **Google Vertex AI (Gemini)** and **Ollama**. This bot features advanced memory systems, autonomous media generation, and a robust permission-based configuration.

---

## Key Features

*   **Dual-Layer Memory**: Sophisticated memory system that tracks both global facts and individual user preferences/history.
*   **Autonomous Media Generation**: AI can proactively generate Images (Imagen 4.0), Videos (Veo 2.0), and Songs (Lyria) based on text descriptions.
*   **User Personalities**: Authorized users can set a custom personality for the AI when interacting with them in DMs.
*   **Multi-Backend support**: Seamlessly switch between Google Gemini (Cloud) and Ollama (Local) for text generation.
*   **Granular Permissions**: Control access to images, videos, songs, and personality features on a per-user basis.
*   **Auto-Installer**: No more manual `pip install`. The bot checks and installs missing dependencies automatically on startup.
*   **Advanced Cooldowns**: Supports global cooldowns and per-channel overrides.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.8+**
- **Google Cloud Project**: Vertex AI enabled with `vertex-credentials.json` in the root folder.
- **Ollama (Optional)**: For local inference.

### 2. Configuration
Create a `.env` file:
```env
DISCORD_TOKEN=your_token_here
GEMINI_API_KEY=your_google_api_key_here  # Optional: for Lyria song generation
```

### 3. Running
*   **Windows**: Run `install.bat`
*   **Linux**: `chmod +x install.sh && ./install.sh`

---

## Commands

### AI Interaction
| Command | Description |
| :--- | :--- |
| `!self <prompt>` | Talk directly to the AI (ignores self-pings). |
| `!backend <gemini/ollama>` | Switch the AI text generation engine. |
| `!models list/set <model>` | List or set active text models. |
| `!status` | Show system uptime and service connection status. |

### Media Generation
| Command | Description |
| :--- | :--- |
| `!image <prompt>` | Generate a high-quality AI image. |
| `!video <prompt>` | Create an AI video (takes a few minutes to render). |
| `!song <prompt>` | Produce an AI song with lyrics and audio. |
| `!toggle <feature>` | Globally enable/disable `image`, `video`, or `song` features. |

### Memory & Personalities
| Command | Description |
| :--- | :--- |
| `!personality <text>` | Set your custom AI personality (DMs only). |
| `!personality view [@u]` | View the current personality of yourself or a user. |
| `!personality clear` | Remove your custom personality. |
| `!memories all` | List all saved global and user memories. |
| `!memories delete ...` | Selective deletion of memories (see `!memories` for help). |
| `!remember <text>` | Manually add a memory. |

### 🛠️ Administration
| Command | Description |
| :--- | :--- |
| `!user info <@u>` | View detailed permissions and status for a user. |
| `!user allow/deny <@u> <perm>`| Manage permissions (`image`, `video`, `song`, `personality`). |
| `!user ban/unban <@u>` | Restrict or restore access to the bot. |
| `!channel add/remove [id]` | Manage allowed channels for the bot. |
| `!channel cooldown <s/off>` | Set/remove specific cooldown for the current channel. |
| `!refresh` | Restart the bot process. |
| `!byebye` | Shutdown the bot. |

---

## AI Autonomous Tags

The AI is trained to manage its own state using specialized tags. You can also use these tags in your prompts:

*   **Memory Management**:
    *   `[GLOBALMEM: <fact>]`: Saves a fact for everyone.
    *   `[USERMEM: <fact>]`: Saves a fact about the current user.
    *   `[DELMEM: <text>]`: Removes a user-specific fact.
*   **Media Triggering**:
    *   `[IMAGE: <prompt>]`: Triggers image generation.
    *   `[VIDEO: <prompt>]`: Triggers video generation.
    *   `[SONG: <prompt>]`: Triggers song generation.

---

## Project Structure

- `bot.py`: Core application logic and event handling.
- `config.json`: Persistent settings, permissions, and channel lists.
- `instructions.txt`: System instructions for AI behavior.
- `vertex-credentials.json`: Google Cloud service account key.
- `user_personalities.json`: Storage for custom user-defined AI behaviors.
- `user_memories.json` / `global_memory.txt`: The bot's long-term databases.

---

> [!CAUTION]
> This is a self-bot. Using self-bots is against Discord's Terms of Service. **Use at your own risk.**
