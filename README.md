# NOVA AI - Autonomous Multi-Platform Agent Ecosystem

Nova AI is an autonomous, multi-platform AI agent ecosystem designed for high-performance desktop workflow automation, mobile WhatsApp integration, and 24/7 Discord community management.

---

## Architecture Overview

1. **Master Desktop Studio**: Executive desktop assistant built with PySide6, featuring full-stack code execution, real-time token streaming, screen vision, cross-platform task scheduling, and live activity monitoring.
2. **WhatsApp Web Bridge**: Baileys WebSocket gateway providing remote device control, autonomous chat management, and live screenshot dispatching (`!screen`, `!pc <cmd>`, `!pctasks`, `!pcstats`, `!stop`, `!start`).
3. **Discord Superbot**: Comprehensive Discord agent with multimodal vision, system administration, secret vault encryption, support tickets, and desktop management (`!screen`, `!pc <action>`, `!pctasks`, `!pcstats`, `!secret`).
4. **Autonomous Tasks & Automations**: Dual-tier scheduling daemon supporting recurring daily routines and same-day scheduled tasks with multi-channel dispatch (Desktop Toast, WhatsApp, Discord).
5. **Central Admin Live Feed**: Bidirectional event bus syncing conversations and command executions across all platforms via local bridge (`http://127.0.0.1:5050/feed`).

---

## Deployment Options

### 1. Local Desktop Studio (Windows)

Requirements:
- Python 3.10+
- Node.js 18+ (for local WhatsApp bridge)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Launch Master Studio
python main.py
```
Alternatively, double-click **`Nova_AI.bat`** on your Desktop.

---

### 2. Cloud 24/7 Hosting on Render (WhatsApp + Discord Bots)

The repository includes native configuration files for 1-click container deployment on Render:
- `render.yaml` : Blueprint definition for automated provisioning
- `Dockerfile` : Multi-runtime Debian environment with Node.js 20, Python 3, and FFmpeg

#### Steps to Deploy on Render:
1. Push this repository to your GitHub account under repository name `Nova`.
2. Log into [Render.com](https://render.com) and click **New +** -> **Blueprint**.
3. Connect your `Nova` GitHub repository. Render will automatically detect `render.yaml` and `Dockerfile`.
4. In the Environment Variables section, configure:
   - `GROQ_API_KEY` : Your Groq API key for high-speed LLM inference.
   - `DISCORD_BOT_TOKEN` : Your Discord Bot Token (from Discord Developer Portal).
   - `OWNER_NAME` : Your chosen administrator username.
   - `OWNER_NUMBERS` : Comma-separated WhatsApp phone numbers authorized for administration.
   - `PORT` : `3000` (default)
5. Click **Apply**. Render will build the container and maintain your 24/7 cloud instance with automatic health pings.

---

## Remote Management Commands

| Command | Channel | Action |
| :--- | :--- | :--- |
| `!screen` | WhatsApp & Discord | Captures current desktop display and returns high-resolution image |
| `!pc <command>` | WhatsApp & Discord | Executes remote application or command on host PC |
| `!pctasks` | WhatsApp & Discord | Queries status of active autonomous scheduled tasks |
| `!pcstats` | WhatsApp & Discord | Dispatches live hardware diagnostic report (CPU, RAM, Disk) |
| `!stop` / `!start` | WhatsApp | Toggles auto-responder on or off for the current conversation |
| `!secret <key>` | Discord | Stores or retrieves encrypted credentials in Nova Vault |

---

## Environment Variables Reference

See `.env.example` for the full template:
```env
GROQ_API_KEY=
DISCORD_BOT_TOKEN=
OWNER_NAME=Admin
OWNER_NUMBERS=
OWNER_DISCORD_IDS=
EMAIL_USER=
EMAIL_PASS=
EMAIL_SMTP=smtp.gmail.com
EMAIL_PORT=587
PORT=3000
```
