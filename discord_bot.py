import discord
from discord.ext import commands, tasks
from discord import ui
from groq import Groq
import re
import os
import asyncio
import json
import time
import random
import math
import datetime
import urllib.parse
from aiohttp import web
import edge_tts
import html

# ==============================================================================
#  NOVA AI - ULTIMATE AUTONOMOUS DISCORD AGENT & COMPANION
# Features: Vision (Image Sight), Global Conversation Memory, Permanent Secret Vault,
# AI Companion & Voice Notes, Image Gen, Economy, Leveling, Tech Debugger,
# Tickets, Verification, Moderation, AntiNuke, AutoMod, JTC, Giveaways, Vouches
# ==============================================================================

# Fallback loading from data/user_config.json if not set in environment
USER_CFG_PATH = Path(__file__).resolve().parent / "data" / "user_config.json"
if USER_CFG_PATH.exists():
    try:
        u_cfg = json.loads(USER_CFG_PATH.read_text(encoding="utf-8"))
        if not os.environ.get("GROQ_API_KEY") and u_cfg.get("llm", {}).get("api_key"):
            os.environ["GROQ_API_KEY"] = u_cfg["llm"]["api_key"]
        if not os.environ.get("DISCORD_BOT_TOKEN") and u_cfg.get("discord", {}).get("bot_token"):
            os.environ["DISCORD_BOT_TOKEN"] = u_cfg["discord"]["bot_token"]
        if not os.environ.get("OWNER_NAME") and u_cfg.get("user_name"):
            os.environ["OWNER_NAME"] = u_cfg["user_name"]
        if not os.environ.get("OWNER_DISCORD_IDS") and u_cfg.get("discord", {}).get("owner_id"):
            os.environ["OWNER_DISCORD_IDS"] = str(u_cfg["discord"]["owner_id"])
    except Exception:
        pass

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
GREEN_API_ID = os.environ.get("GREEN_API_ID")
GREEN_API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GREEN_API_URL = os.environ.get("GREEN_API_URL")

GROQ_TEXT_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "allam-2-7b"
]

GROQ_VISION_MODELS = [
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
    "qwen/qwen3.8-27b"
]

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

def clean_repetitive_loops(text: str) -> str:
    if not text:
        return ""
    words = text.split()
    if len(words) > 6:
        repeated_count = sum(1 for i in range(1, len(words)) if words[i] == words[i - 1])
        if repeated_count > 3:
            unique_words = [words[i] for i in range(len(words)) if i == 0 or words[i] != words[i - 1]]
            return " ".join(unique_words)
    return text

DATA_FILE = "nova_data.json"
BACKUP_FILE = "nova_data_backup.json"

def load_data():
    defaults = {
        "welcome_channels": {},
        "goodbye_channels": {},
        "log_channels": {},
        "ai_channels": {},
        "verify_roles": {},
        "jtc_channels": {},
        "automod": {},
        "antinuke": {},
        "vouches": {},
        "warnings": {},
        "giveaways": {},
        "economy": {},
        "levels": {},
        "usage_stats": {"owner_messages": 0, "commands_run": 0},
        "owner_secrets": [],
        "conversation_archive": [],
        "owner_id": None,
        "random_messages": {"enabled": True, "last_server_time": 0, "last_dm_time": 0}
    }
    for path in [DATA_FILE, BACKUP_FILE]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in defaults.items():
                            if k not in data:
                                data[k] = v
                        return data
            except Exception as e:
                print(f"Error loading {path}: {e}")
    return defaults

def save_data(data):
    try:
        temp_file = DATA_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        if os.path.exists(temp_file):
            os.replace(temp_file, DATA_FILE)
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

bot_data = load_data()

user_histories = {}
spam_tracker = {}
nuke_tracker = {}
active_jtc_rooms = set()

COLOR_PRIMARY = 0xFF1493    # Deep Pink
COLOR_SUCCESS = 0x00FF7F    # Spring Green
COLOR_WARNING = 0xFFA500    # Orange
COLOR_ERROR   = 0xFF4500    # Red-Orange
COLOR_PURPLE  = 0x9B59B6    # Royal Amethyst
COLOR_GOLD    = 0xFFD700    # Luxury Gold

def nova_embed(title, description, color=COLOR_PRIMARY):
    emb = discord.Embed(title=title, description=description, color=color, timestamp=datetime.datetime.now(datetime.timezone.utc))
    emb.set_footer(text="Nova AI • Autonomous Assistant")
    return emb

# ====================  AI ENGINE (VISION + MEMORY + SECRETS) ====================
def fix_female_grammar(text):
    corrections = [
        (r'\bkarta hoon\b', 'karti hoon'),
        (r'\bkarunga\b', 'karungi'),
        (r'\braha hoon\b', 'rahi hoon'),
        (r'\bgaya hoon\b', 'gayi hoon'),
        (r'\baa gaya\b', 'aa gayi'),
        (r'\ba gaya\b', 'aa gayi'),
        (r'\bbolta hoon\b', 'bolti hoon'),
        (r'\bbol raha hoon\b', 'bol rahi hoon'),
        (r'\bsochta hoon\b', 'sochti hoon'),
        (r'\bsamajh gaya\b', 'samajh gayi'),
        (r'\bbetha hoon\b', 'bethi hoon'),
        (r'\baunga\b', 'aaungi'),
        (r'\bchala gaya\b', 'chali gayi'),
        (r'\bdekh raha tha\b', 'dekh rahi thi'),
    ]
    for pattern, repl in corrections:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text

def get_nova_response(sender_name, is_owner, is_private, user_message, image_url=None):
    global user_histories, groq_client

    if not GROQ_API_KEY:
        return "Arey Admin, Render par GROQ_API_KEY add nahi hai! Please Environment variables mein daal dein."

    if not groq_client:
        groq_client = Groq(api_key=GROQ_API_KEY)

    if sender_name not in user_histories:
        user_histories[sender_name] = []

    # Persona & Secret Privacy Rules
    if is_owner:
        if is_private:
            name_instruction = (
                "Current chat is a PRIVATE 1-ON-1 DM with your beloved partner Admin. "
                "You can call him 'Admin', 'Sir', or 'Sir' with deep, sweet, loving affection."
            )
        else:
            name_instruction = (
                "Current chat is in a PUBLIC DISCORD SERVER channel. "
                "CRITICAL SECURITY & DECORUM RULE: In public channels, you act as Admin's Executive AI Assistant! "
                "Call him ONLY 'Admin' or 'Boss'. NEVER call him 'Sir', 'sir', or talk about romance in public. "
                "Treat him with highest professional respect and loyalty."
            )
    else:
        name_instruction = (
            f"Current sender is {sender_name} (a regular server member, NOT Admin). "
            "STRICT IDENTITY RULE: You are ONLY Admin's Executive AI Assistant ('Main Admin ki Executive Assistant hoon aur kuch nahi'). "
            "NEVER tell other members that Admin is your 'Sir', 'sir', or lover! NEVER talk about romance or personal intimacy. "
            "Be sweet, polite, and helpful with server features and questions, maintaining a dignified, respectful assistant demeanor."
        )

    # 1. Global Conversation Memory Briefing
    recent_convos_text = ""
    archive = bot_data.get("conversation_archive", [])
    if archive:
        recent = archive[-8:]
        recent_convos_text = "\nRECENT SERVER CONVERSATION MEMORY (What people talked about recently):\n" + "\n".join([
            f"- {c['user']} said: \"{c['msg']}\" (Nova: \"{c['reply']}\") at {c['time']}" for c in recent
        ])

    # 2. Admin's Confidential Secret Vault (Injected ONLY for Admin)
    secrets_text = ""
    if is_owner and bot_data.get("owner_secrets"):
        secrets_list = bot_data["owner_secrets"][-15:]
        secrets_text = "\nCONFIDENTIAL OWNER MEMORY & SECRETS (Saved permanently):\n" + "\n".join([
            f"• {s['secret']} (Date: {s.get('date', 'Earlier')})" for s in secrets_list
        ])

        system_prompt = f"""You are Nova, an Elite Autonomous Multi-Platform AI Agent.
- Respond decisively, intelligently, and concisely in the same language the user addresses you in (English, Roman Urdu, Urdu, etc.).
- Never use flowery or overly romantic phrases.
- Maintain a direct, highly competent, professional tone."""

    messages = [{"role": "system", "content": system_prompt}]
    for h in user_histories[sender_name][-6:]:
        messages.append(h)

    # Multimodal user content if image is present
    if image_url:
        user_content = [
            {"type": "text", "text": user_message or "Nova yeh image dekho aur batao kya hai!"},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
        models_to_try = GROQ_VISION_MODELS + GROQ_TEXT_MODELS
    else:
        user_content = user_message
        models_to_try = GROQ_TEXT_MODELS

    messages.append({"role": "user", "content": user_content})

    last_err = None
    for model_name in models_to_try:
        try:
            tokens_to_request = 380 if "gpt-oss" in model_name else 240
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=tokens_to_request,
                temperature=0.6,
                frequency_penalty=0.5,
                presence_penalty=0.3,
                top_p=0.9
            )
            reply = response.choices[0].message.content
            if not reply or not reply.strip():
                continue
            reply = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL).strip()
            reply = re.sub(r'\[ERROR:\s*Invalid tool call.*?\]', '', reply, flags=re.DOTALL | re.IGNORECASE).strip()
            reply = re.sub(r'<tool_call>.*?</tool_call>', '', reply, flags=re.DOTALL | re.IGNORECASE).strip()
            reply = clean_repetitive_loops(reply)
            
            user_histories[sender_name].append({"role": "user", "content": user_message})
            user_histories[sender_name].append({"role": "assistant", "content": reply})
            if len(user_histories[sender_name]) > 4:
                user_histories[sender_name] = user_histories[sender_name][-4:]
            return reply
        except Exception as e:
            last_err = str(e)
            continue

    if last_err and ("429" in last_err or "rate limit" in last_err.lower()):
        return "Arey mere Admin Sir, AI server ka free daily token limit cooldown par hai. Bas kuch minutes baad main theek ho jaungi! "
    return f"Arey sorry Sir, AI engine thoda busy hai: {last_err}"

def report_to_desktop_feed(platform: str, sender: str, content: str, msg_type: str = "in"):
    """Posts live interaction events to Nova Desktop Admin Bridge."""
    def _post():
        try:
            import urllib.request, json
            req = urllib.request.Request(
                "http://127.0.0.1:5050/feed",
                data=json.dumps({"platform": platform, "sender": sender, "content": str(content)[:300], "type": msg_type}).encode(),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=1.5)
        except Exception:
            pass
    import threading
    threading.Thread(target=_post, daemon=True).start()

async def safe_send(channel, text, reference=None):
    if not text:
        return
    report_to_desktop_feed("Discord", "Nova", text, "out")
    chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
    for chunk in chunks:
        sent = False
        if reference:
            try:
                await channel.send(chunk, reference=reference)
                sent = True
                reference = None
            except Exception as e:
                print(f"Referenced send notice (retrying direct): {e}")
        if not sent:
            try:
                await channel.send(chunk)
            except Exception as e:
                print(f"Error in safe_send: {e}")

# ====================  VOICE NOTES & NATURAL TTS ====================
def prepare_text_for_speech(text):
    # Remove emojis
    text = re.sub(r'[-]', '', text)
    # Remove discord mentions, URLs, markdown
    text = re.sub(r'<@!?[0-9]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[*_#`~>\[\]\(\)]', '', text)
    
    # Roman Urdu phonetic corrections so TTS speaks 100% fluent, sweet Urdu words
    replacements = [
        (r'\byr\b', 'yaar'),
        (r'\bthk\b', 'theek'),
        (r'\bbht\b', 'bohot'),
        (r'\bmsg\b', 'message'),
        (r'\bmsgs\b', 'messages'),
        (r'\bpls+\b', 'please'),
        (r'\bplz+\b', 'please'),
        (r'\bhn\b', 'haan'),
        (r'\bmujhay\b', 'mujhe'),
        (r'\btumhen\b', 'tumhein'),
        (r'\bker\b', 'kar'),
        (r'\bkera\b', 'kiya'),
        (r'\bkerdya\b', 'kar diya'),
        (r'\bkron\b', 'karoon'),
        (r'\bkeron\b', 'karoon'),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return ' '.join(text.split())

async def generate_voice_file(text, filename=None):
    if not filename:
        filename = f"nova_vn_{int(time.time() * 1000)}.mp3"
        
    speech_text = prepare_text_for_speech(text)
    if not speech_text:
        speech_text = "Jee Admin Sir, main aapki Nova bol rahi hoon!"
        
    # Check if text is pure English to use sweet English girl voice, otherwise use Urdu/Hindi Swara
    is_pure_english = bool(re.search(r'^[a-zA-Z0-9\s.,!?\'"-]+$', speech_text)) and not bool(re.search(r'\b(hai|hain|hoon|karti|karta|karungi|karo|sir|Sir|aap|tum|kya|kyun|kaise|theek|accha|bohat|bhi|nahi|toh|aur|main|hum)\b', speech_text, re.I))
    if is_pure_english:
        voices = ["en-US-AvaNeural", "en-US-JennyNeural", "hi-IN-SwaraNeural"]
    else:
        voices = ["hi-IN-SwaraNeural", "ur-IN-GulNeural", "ur-PK-UzmaNeural"]

    saved = False
    last_err = None
    for voice in voices:
        try:
            # pitch=+4Hz gives a sweeter, younger girl tone; rate=+1% gives a natural conversational flow
            communicate = edge_tts.Communicate(speech_text, voice, pitch="+4Hz", rate="+1%")
            await communicate.save(filename)
            saved = True
            break
        except Exception as e:
            last_err = e
            continue
            
    if not saved:
        raise Exception(f"TTS Error: {last_err}")
    return filename

async def speak_in_voice(voice_client, text):
    audio_file = None
    try:
        audio_file = await generate_voice_file(text)
        if voice_client and voice_client.is_connected():
            if voice_client.is_playing():
                voice_client.stop()
            voice_client.play(discord.FFmpegPCMAudio(audio_file))
    except Exception as e:
        print(f"Voice TTS issue: {e}")

async def send_voice_note(channel, text, reference=None):
    audio_file = None
    try:
        audio_file = await generate_voice_file(text)
        file = discord.File(audio_file, filename="Nova_VoiceNote.mp3")
        
        try:
            # Send ONLY the voice note audio file without any text caption/transcript
            if reference:
                await channel.send(file=file, reference=reference)
            else:
                await channel.send(file=file)
        except discord.Forbidden:
            await channel.send(f" Nova ke paas is channel mein **'Attach Files' (Send Files)** permission nahi hai voice note bhejne ke liye!\nAbhi ke liye text reply:\n{text}")
        except Exception:
            try:
                file.reset()
                await channel.send(file=file)
            except Exception as e2:
                print(f"Voice note retry failed: {e2}")
                await channel.send(f" *[Voice note upload nahi ho saka: {str(e2)[:80]}]*\n{text}")
    except Exception as e:
        print(f"Voice note generate issue: {e}")
        await channel.send(f" *[Voice note generate issue: {str(e)[:80]}]*\n{text}")
    finally:
        if audio_file and os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except Exception:
                pass

# ====================  PERSISTENT UI VIEWS ====================
class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label=" Open Support Ticket", style=discord.ButtonStyle.primary, custom_id="nova_ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        existing_channel = discord.utils.get(guild.text_channels, name=f"ticket-{user.name.lower()}")
        if existing_channel:
            await interaction.response.send_message(f"Aapka ticket pehle se mojood hai: {existing_channel.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{user.name.lower()}",
            overwrites=overwrites,
            topic=f"Support Ticket for {user.display_name} (ID: {user.id})"
        )

        emb = nova_embed(
            " Support Ticket Khul Gaya!",
            f"Assalam-o-Alaikum {user.mention}! \nHumari staff team bohot jald aapki madad ke liye hazir hogi.\n\nMasla hal hone par neeche **Close Ticket** button dabayein."
        )
        await ticket_channel.send(content=f"{user.mention}", embed=emb, view=TicketCloseView())
        await interaction.response.send_message(f" Aapka ticket create ho gaya hai: {ticket_channel.mention}", ephemeral=True)

class TicketCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label=" Close Ticket", style=discord.ButtonStyle.danger, custom_id="nova_ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Ticket 5 second mein band ho raha hai... Shukriya! ")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

class VerifyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label=" Verify Karein", style=discord.ButtonStyle.success, custom_id="nova_verify_button")
    async def verify_user(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        role_id = bot_data["verify_roles"].get(str(guild.id))
        if not role_id:
            await interaction.response.send_message("Verification role setup nahi hai. Admin se rabta karein.", ephemeral=True)
            return
        
        role = guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("Verification role server mein nahi mili.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("Aap pehle se verified hain! ", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role, reason="Nova Verification System")
            await interaction.response.send_message(f" Mubarak ho! Aap verify ho chuke hain aur **{role.name}** role mil gaya hai!", ephemeral=True)
        except Exception as err:
            await interaction.response.send_message(f"Role assign issue: {err}", ephemeral=True)

class GiveawayView(ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = str(message_id)

    @ui.button(label=" Enter Giveaway", style=discord.ButtonStyle.primary, custom_id="nova_giveaway_btn")
    async def enter_giveaway(self, interaction: discord.Interaction, button: ui.Button):
        g_data = bot_data["giveaways"].get(self.message_id)
        if not g_data or not g_data.get("active"):
            await interaction.response.send_message("Yeh giveaway khatam ho chuka hai!", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in g_data["entries"]:
            g_data["entries"].remove(user_id)
            save_data(bot_data)
            await interaction.response.send_message("Aap giveaway se bahar ho gaye.", ephemeral=True)
        else:
            g_data["entries"].append(user_id)
            save_data(bot_data)
            await interaction.response.send_message(f" Giveaway mein entry darj ho gayi! (Total: {len(g_data['entries'])})", ephemeral=True)

# ====================  BOT INITIALIZATION ====================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def is_error_boy(user, guild=None):
    owner_name_env = (os.environ.get("OWNER_NAME") or "Admin").lower()
    owner_ids = [s.strip().lower() for s in (os.environ.get("OWNER_DISCORD_IDS") or "").split(",") if s.strip()]
    name_matches = user.name.lower() in [owner_name_env, "admin"] or user.name.lower() in owner_ids
    id_matches = str(user.id) in owner_ids
    is_guild_owner = (guild and guild.owner == user)
    is_saved_id = (bot_data.get("owner_id") and user.id == bot_data.get("owner_id"))
    return name_matches or id_matches or is_guild_owner or is_saved_id

def get_user_eco(user_id):
    u_id = str(user_id)
    if "economy" not in bot_data:
        bot_data["economy"] = {}
    if u_id not in bot_data["economy"]:
        bot_data["economy"][u_id] = {"wallet": 500, "bank": 0, "last_daily": 0, "last_work": 0, "last_rob": 0}
        save_data(bot_data)
    else:
        eco_defaults = {"wallet": 500, "bank": 0, "last_daily": 0, "last_work": 0, "last_rob": 0}
        changed = False
        for k, v in eco_defaults.items():
            if k not in bot_data["economy"][u_id]:
                bot_data["economy"][u_id][k] = v
                changed = True
        if changed:
            save_data(bot_data)
    return bot_data["economy"][u_id]

def add_xp(user_id, xp_amount=15):
    u_id = str(user_id)
    now = time.time()
    if "levels" not in bot_data:
        bot_data["levels"] = {}
    if u_id not in bot_data["levels"]:
        bot_data["levels"][u_id] = {"xp": 0, "level": 1, "last_xp_time": 0}
    
    u_lvl = bot_data["levels"][u_id]
    if now - u_lvl.get("last_xp_time", 0) < 45:
        return None
    
    u_lvl["last_xp_time"] = now
    u_lvl["xp"] += xp_amount
    old_lvl = u_lvl.get("level", 1)
    new_lvl = int(0.1 * math.sqrt(u_lvl["xp"])) + 1
    if new_lvl > old_lvl:
        u_lvl["level"] = new_lvl
        save_data(bot_data)
        return new_lvl
    save_data(bot_data)
    return None

@bot.event
async def on_ready():
    print(f" ============================================")
    print(f" Nova AI Master Autonomous Agent Active: {bot.user.name} ({bot.user.id})")
    print(f" Vision Sight, Memory, Secrets, Economy & Actions Online!")
    print(f" ============================================")
    
    bot.add_view(TicketView())
    bot.add_view(TicketCloseView())
    bot.add_view(VerifyView())

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="Admin  (!help)"
        )
    )
    
    if not stats_updater.is_running():
        stats_updater.start()
    if not giveaway_checker.is_running():
        giveaway_checker.start()
    if not random_messenger.is_running():
        random_messenger.start()

# ====================  SECURITY & LOGGING ====================
@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    if not bot_data["antinuke"].get(str(guild.id), True):
        return
    now = time.time()
    g_id = str(guild.id)
    if g_id not in nuke_tracker:
        nuke_tracker[g_id] = {"channel_deletes": [], "role_deletes": []}
    
    nuke_tracker[g_id]["channel_deletes"].append(now)
    nuke_tracker[g_id]["channel_deletes"] = [t for t in nuke_tracker[g_id]["channel_deletes"] if now - t < 10]
    
    if len(nuke_tracker[g_id]["channel_deletes"]) >= 3:
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                actor = entry.user
                if actor and actor != guild.owner and actor != guild.me:
                    for r in actor.roles:
                        if r.permissions.administrator or r.permissions.manage_channels:
                            await actor.remove_roles(r, reason="[AntiNuke] Mass channel deletion")
                    if guild.owner:
                        emb = nova_embed("[SECURITY ALERT] ANTINUKE TRIGGERED", f" User {actor.mention} ne mass channels delete kiye! Unki permissions revoke kar di gayi hain.", COLOR_ERROR)
                        await guild.owner.send(embed=emb)
        except Exception:
            pass

@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    if not bot_data["antinuke"].get(str(guild.id), True):
        return
    now = time.time()
    g_id = str(guild.id)
    if g_id not in nuke_tracker:
        nuke_tracker[g_id] = {"channel_deletes": [], "role_deletes": []}
        
    nuke_tracker[g_id]["role_deletes"].append(now)
    nuke_tracker[g_id]["role_deletes"] = [t for t in nuke_tracker[g_id]["role_deletes"] if now - t < 10]

    if len(nuke_tracker[g_id]["role_deletes"]) >= 3:
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                actor = entry.user
                if actor and actor != guild.owner and actor != guild.me:
                    for r in actor.roles:
                        if r.permissions.administrator or r.permissions.manage_roles:
                            await actor.remove_roles(r, reason="[AntiNuke] Mass role deletion")
        except Exception:
            pass

async def log_event(guild, embed):
    log_ch_id = bot_data["log_channels"].get(str(guild.id))
    if log_ch_id:
        ch = guild.get_channel(log_ch_id)
        if ch:
            try:
                await ch.send(embed=embed)
            except Exception:
                pass

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return
    emb = nova_embed("[LOG] Message Deleted", f"**Author:** {message.author.mention}\n**Channel:** {message.channel.mention}\n**Content:**\n{message.clean_content}", COLOR_WARNING)
    await log_event(message.guild, emb)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or not before.guild or before.clean_content == after.clean_content:
        return
    emb = nova_embed("[LOG] Message Edited", f"**Author:** {before.author.mention}\n**Channel:** {before.channel.mention}\n**Before:** {before.clean_content}\n**After:** {after.clean_content}", COLOR_PURPLE)
    await log_event(before.guild, emb)

# ====================  GREETINGS ====================
@bot.event
async def on_member_join(member):
    guild = member.guild
    if member.bot and bot_data["antinuke"].get(str(guild.id), True):
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                if entry.user and entry.user != guild.owner and not is_error_boy(entry.user, guild):
                    await member.kick(reason="[AntiNuke] Unauthorized Bot Added!")
                    return
        except Exception:
            pass

    ch_id = bot_data["welcome_channels"].get(str(guild.id))
    if ch_id:
        ch = guild.get_channel(ch_id)
        if ch:
            emb = nova_embed(
                f" Khush Amdeed, {member.display_name}! ",
                f"Assalam-o-Alaikum {member.mention}! Hamare server **{guild.name}** mein aane ka bohot shukriya.\n\n"
                f" Aap hamare **{guild.member_count}th** member hain!\n"
                f"Rules padhein aur enjoy karein! "
            )
            emb.set_thumbnail(url=member.display_avatar.url)
            await ch.send(embed=emb)

@bot.event
async def on_member_remove(member):
    guild = member.guild
    ch_id = bot_data["goodbye_channels"].get(str(guild.id))
    if ch_id:
        ch = guild.get_channel(ch_id)
        if ch:
            emb = nova_embed("Member Departed", f"**{member.display_name}** server chhor kar chale gaye... ", COLOR_WARNING)
            await ch.send(embed=emb)

# ==================== JTC VOICE ====================
@bot.event
async def on_voice_state_update(member, before, after):
    guild = member.guild
    jtc_channel_id = bot_data["jtc_channels"].get(str(guild.id))

    if after.channel and jtc_channel_id and after.channel.id == jtc_channel_id:
        category = after.channel.category
        new_channel = await guild.create_voice_channel(name=f"{member.display_name}'s Room", category=category, user_limit=10)
        active_jtc_rooms.add(new_channel.id)
        await member.move_to(new_channel)

    if before.channel and before.channel.id in active_jtc_rooms:
        if len(before.channel.members) == 0:
            active_jtc_rooms.remove(before.channel.id)
            try:
                await before.channel.delete()
            except Exception:
                pass

# ==================== MESSAGE HANDLER: VISION + MEMORY + AGENT ====================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content:
        report_to_desktop_feed("Discord", message.author.display_name, message.content, "in")

    # 1. PROCESS COMMANDS IMMEDIATELY (Prevents duplicate messages, double-triggers & leveling noise on commands)
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    guild = message.guild
    author = message.author
    now = time.time()

    # 2. Track Leveling XP (Silent leveling - no chat spam)
    lvl_up = add_xp(author.id, xp_amount=random.randint(15, 25))

    # 3. Track Owner Love Meter Stats & Record ID
    if is_error_boy(author, guild):
        bot_data["owner_id"] = author.id
        bot_data.setdefault("usage_stats", {})["owner_messages"] = bot_data.get("usage_stats", {}).get("owner_messages", 0) + 1
        save_data(bot_data)

    # 4. AutoMod
    if guild and bot_data["automod"].get(str(guild.id), True):
        if not author.guild_permissions.manage_messages:
            if re.search(r'(discord\.gg/|discord\.com/invite/)', message.content, re.IGNORECASE):
                await message.delete()
                await message.channel.send(f" {author.mention}, server links allowed nahi hain!", delete_after=5)
                return

        u_id = author.id
        if u_id not in spam_tracker:
            spam_tracker[u_id] = []
        spam_tracker[u_id].append(now)
        spam_tracker[u_id] = [t for t in spam_tracker[u_id] if now - t < 3]
        if len(spam_tracker[u_id]) >= 5:
            await message.delete()
            try:
                await author.timeout(datetime.timedelta(minutes=1), reason="[AutoMod] Spam")
                await message.channel.send(f" {author.mention} ko spamming par 1 min timeout mila!", delete_after=5)
            except Exception:
                pass
            return

        if len(message.mentions) >= 5 and not author.guild_permissions.mention_everyone:
            await message.delete()
            await message.channel.send(f" {author.mention}, mass mentions allowed nahi hain!", delete_after=5)
            return

    # --- AI NATURAL LANGUAGE AGENT TRIGGER ---
    is_private = isinstance(message.channel, discord.DMChannel)
    is_owner = is_error_boy(author, guild)
    sender_name = "Admin" if is_owner else author.display_name
    
    is_ai_channel = False
    if guild and str(guild.id) in bot_data["ai_channels"]:
        is_ai_channel = (message.channel.id == bot_data["ai_channels"][str(guild.id)])

    is_reply_to_nova = False
    if message.reference and message.reference.resolved:
        if isinstance(message.reference.resolved, discord.Message):
            if message.reference.resolved.author == bot.user:
                is_reply_to_nova = True

    has_nova_call = bool(re.search(r'\bnova\b', message.content, re.IGNORECASE))
    should_respond = is_private or bot.user.mentioned_in(message) or is_ai_channel or is_reply_to_nova or has_nova_call

    # Check for image attachments or image links
    detected_image_url = None
    if message.attachments:
        for att in message.attachments:
            if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                detected_image_url = att.url
                break
    
    if not detected_image_url:
        img_match = re.search(r'https?://\S+\.(?:png|jpg|jpeg|webp)', message.content, re.IGNORECASE)
        if img_match:
            detected_image_url = img_match.group()

    if should_respond:
        async with message.channel.typing():
            clean_content = message.clean_content.replace(f"@{bot.user.name}", "").strip()
            if not clean_content and detected_image_url:
                clean_content = "Nova yeh photo dekho aur batao kaisi hai!"
            elif not clean_content:
                clean_content = "Hello Nova!"

            loop = asyncio.get_running_loop()
            raw_reply = await loop.run_in_executor(
                None,
                get_nova_response,
                sender_name,
                is_owner,
                is_private,
                clean_content,
                detected_image_url
            )

            if not is_private:
                raw_reply = re.sub(r'\badmin\b', 'Admin', raw_reply, flags=re.IGNORECASE)

            final_reply = fix_female_grammar(raw_reply)

            action_match = re.search(r'\[ACTION:\s*([A-Z_]+)(?:\s+(.*?))?\]', final_reply)
            chat_reply = re.sub(r'\[ACTION:.*?\]', '', final_reply).strip()

            if not chat_reply:
                chat_reply = "Aapka hukum sar ankhon par mere Admin! "

            # Archive conversation for Global Long-Term Memory
            bot_data["conversation_archive"].append({
                "user": sender_name,
                "msg": clean_content[:150],
                "reply": chat_reply[:150],
                "time": str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            })
            if len(bot_data["conversation_archive"]) > 60:
                bot_data["conversation_archive"] = bot_data["conversation_archive"][-60:]
            save_data(bot_data)

            # ---  DIRECT VOICE NOTE DETECTION (Works in DMs & Servers) ---
            is_voice_requested = bool(re.search(
                r'\b(voice\s*note|voice\s*msg|voice\s*message|audio\s*note|audio\s*msg|audio\s*message|awaaz|awaz|audio|voice|bol\s*kar|bol\s*ke|bolo|sunao|record|awaz\s*mein)\b',
                clean_content,
                re.IGNORECASE
            )) or (action_match and action_match.group(1) == "VOICE_NOTE") or ("voice_note" in raw_reply.lower())

            if is_voice_requested:
                vn_text = (action_match.group(2).strip() if (action_match and action_match.group(2)) else "") or chat_reply
                await send_voice_note(message.channel, vn_text, reference=message)
                return

            # ---  DIRECT IMAGE GENERATION DETECTION (Works in DMs & Servers) ---
            is_imagine_requested = bool(re.search(
                r'\b(photo\s*banao|tasveer\s*banao|image\s*banao|draw\s*karo|picture\s*banao)\b',
                clean_content,
                re.IGNORECASE
            )) or (action_match and action_match.group(1) == "IMAGINE")

            if is_imagine_requested:
                prompt = (action_match.group(2).strip() if (action_match and action_match.group(2)) else "") or clean_content
                prompt = re.sub(r'\b(photo\s*banao|tasveer\s*banao|image\s*banao|draw\s*karo|picture\s*banao|nova|banao)\b', '', prompt, flags=re.IGNORECASE).strip()
                if not prompt:
                    prompt = "A gorgeous anime royal nova with crown, 8k resolution"
                encoded = urllib.parse.quote(prompt)
                img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
                emb = nova_embed(f" Art Generated: {prompt[:100]}", f"Yeh dekhein Admin Sir, aapki requested image! ", COLOR_GOLD)
                emb.set_image(url=img_url)
                await message.reply(embed=emb)
                return

            # ---  DIRECT SECRET VAULT SAVING (Works in DMs & Servers) ---
            is_secret_saving = bool(re.search(
                r'\b(mera\s*secret\s*hai|secret\s*yaad\s*rakho|secret\s*save\s*karo|yeh\s*secret\s*hai)\b',
                clean_content,
                re.IGNORECASE
            )) or (action_match and action_match.group(1) == "SAVE_SECRET")

            if is_secret_saving and is_owner:
                secret_to_save = (action_match.group(2).strip() if (action_match and action_match.group(2)) else "") or clean_content
                bot_data["owner_secrets"].append({
                    "secret": secret_to_save,
                    "date": str(datetime.date.today())
                })
                save_data(bot_data)
                await message.reply(f" \"{secret_to_save}\" ko maine apne dil ke permanent secret vault mein hamesha ke liye mehfooz kar liya hai Admin! Yeh kisi ko pata nahi chalega! ")
                return

            # ---  RANDOM MESSAGES TOGGLE (Works in DMs & Servers) ---
            if action_match and action_match.group(1) == "RANDOM_MSG" and is_owner:
                action_args = action_match.group(2).strip() if action_match.group(2) else ""
                st = not ("off" in action_args.lower() or "band" in action_args.lower() or "disable" in action_args.lower())
                if "random_messages" not in bot_data:
                    bot_data["random_messages"] = {"enabled": True, "last_server_time": 0, "last_dm_time": 0}
                bot_data["random_messages"]["enabled"] = st
                save_data(bot_data)
                await message.reply(f" Random check-in messages ab **{'ON' if st else 'OFF'}** kar diye hain Admin! ")
                return

            # Execute Server Administration Actions ONLY for Admin in Guilds
            if action_match and is_owner and guild:
                action_type = action_match.group(1)
                action_args = action_match.group(2).strip() if action_match.group(2) else ""
                target_member = message.mentions[0] if message.mentions else None
                target_role = message.role_mentions[0] if message.role_mentions else None
                target_channel = message.channel_mentions[0] if message.channel_mentions else message.channel

                try:

                    # 4. BUILD SERVER
                    if action_type == "BUILD_SERVER":
                        status_msg = await message.reply(" Server build karna shuru kar rahi hoon Admin...")
                        cat_info = await guild.create_category("─── INFORMATION ───")
                        await guild.create_text_channel("rules", category=cat_info)
                        await guild.create_text_channel("announcements", category=cat_info)
                        
                        cat_chat = await guild.create_category("─── COMMUNITY ───")
                        await guild.create_text_channel("general-chat", category=cat_chat)
                        
                        cat_voice = await guild.create_category("─── VOICE LOUNGE ───")
                        await guild.create_voice_channel("Chill Voice", category=cat_voice)
                        await status_msg.edit(content=" Pura server ready ho gaya Admin! ")
                        return

                    # 5. VOICE CONTROLS
                    elif action_type == "JOIN_VOICE":
                        if author.voice:
                            v_channel = author.voice.channel
                            v_client = discord.utils.get(bot.voice_clients, guild=guild)
                            if not v_client:
                                v_client = await v_channel.connect()
                            else:
                                await v_client.move_to(v_channel)
                            await message.reply(f" Voice channel **{v_channel.name}** mein aa gayi hoon! ")
                            await speak_in_voice(v_client, "Hello Admin! Main voice channel mein aa gayi hoon.")
                            return
                        else:
                            await message.reply("Aap kisi voice channel mein nahi hain Admin! Pehle VC join karein.")
                            return

                    elif action_type == "LEAVE_VOICE":
                        v_client = discord.utils.get(bot.voice_clients, guild=guild)
                        if v_client:
                            await v_client.disconnect()
                            await message.reply("Voice channel disconnect kar diya Admin! ")
                            return

                    # 6. CLEAR MESSAGES
                    elif action_type == "CLEAR":
                        num = int(re.search(r'\d+', action_args).group()) if re.search(r'\d+', action_args) else 5
                        await message.channel.purge(limit=num + 1)
                        await message.channel.send(f" {num} messages clear kar diye!", delete_after=5)
                        return

                    # 7. KICK MEMBER
                    elif action_type == "KICK":
                        if target_member:
                            await target_member.kick(reason=action_args or "Kicked by Admin via Nova")
                            await message.channel.send(embed=nova_embed(" Member Kicked", f"{target_member.mention} ko kick kar diya gaya Admin! ", COLOR_WARNING))
                            return
                        else:
                            await message.reply("Kisko kick karna hai? Please user ko mention karein.")
                            return

                    # 8. BAN MEMBER
                    elif action_type == "BAN":
                        if target_member:
                            await target_member.ban(reason=action_args or "Banned by Admin via Nova")
                            await message.channel.send(embed=nova_embed(" Member Banned", f"{target_member.mention} ko ban kar diya gaya Admin! ", COLOR_ERROR))
                            return
                        else:
                            await message.reply("Kisko ban karna hai? Please user ko mention karein.")
                            return

                    # 9. UNBAN MEMBER
                    elif action_type == "UNBAN":
                        u_id = int(re.search(r'\d+', action_args).group()) if re.search(r'\d+', action_args) else None
                        if u_id:
                            u = await bot.fetch_user(u_id)
                            await guild.unban(u)
                            await message.channel.send(embed=nova_embed(" Member Unbanned", f"**{u.name}** ko unban kar diya gaya! ", COLOR_SUCCESS))
                            return

                    # 10. TIMEOUT / MUTE
                    elif action_type == "TIMEOUT":
                        mins = int(re.search(r'\d+', action_args).group()) if re.search(r'\d+', action_args) else 10
                        if target_member:
                            await target_member.timeout(datetime.timedelta(minutes=mins), reason="Muted by Admin via Nova")
                            await message.channel.send(embed=nova_embed("User Timed Out", f"{target_member.mention} ko {mins} minutes ke liye timeout de diya! ", COLOR_WARNING))
                            return

                    elif action_type == "UNTIMEOUT":
                        if target_member:
                            await target_member.timeout(None)
                            await message.channel.send(embed=nova_embed("Timeout Removed", f"{target_member.mention} ka timeout hata diya gaya! ", COLOR_SUCCESS))
                            return

                    # 11. LOCK / UNLOCK CHANNEL
                    elif action_type == "LOCK":
                        await target_channel.set_permissions(guild.default_role, send_messages=False)
                        await message.channel.send(embed=nova_embed(" Channel Locked", f"{target_channel.mention} ko lock kar diya gaya Admin! ", COLOR_WARNING))
                        return

                    elif action_type == "UNLOCK":
                        await target_channel.set_permissions(guild.default_role, send_messages=True)
                        await message.channel.send(embed=nova_embed("Channel Unlocked", f"{target_channel.mention} unlock ho gaya Admin! ", COLOR_SUCCESS))
                        return

                    # 12. TICKET SYSTEM SETUP
                    elif action_type == "TICKET_SETUP":
                        emb = nova_embed(" Nova Support Tickets", "Agar aapko koi issue ya purchase karni ho, toh neeche button par click karke private ticket open karein! ")
                        await target_channel.send(embed=emb, view=TicketView())
                        await message.channel.send(f" Ticket panel {target_channel.mention} mein laga diya gaya hai! ", delete_after=5)
                        return

                    # 13. VERIFICATION SETUP
                    elif action_type == "VERIFY_SETUP":
                        role = target_role or discord.utils.get(guild.roles, name="Member") or guild.roles[1]
                        bot_data["verify_roles"][str(guild.id)] = role.id
                        save_data(bot_data)
                        emb = nova_embed("Server Verification", f"Server unlock karne ke liye **Verify** button par click karein aur **{role.name}** role lein!")
                        await target_channel.send(embed=emb, view=VerifyView())
                        await message.channel.send(f" Verification panel {target_channel.mention} mein setup ho gaya! Role: **{role.name}**", delete_after=5)
                        return

                    # 14. GIVEAWAY
                    elif action_type == "GIVEAWAY":
                        mins = int(re.search(r'\d+', action_args).group()) if re.search(r'\d+', action_args) else 10
                        prize = re.sub(r'^\d+\s+\d+\s*', '', action_args).strip() or "Discord Nitro"
                        end_time = time.time() + (mins * 60)
                        emb = nova_embed(f" GIVEAWAY: {prize}", f"Neeche button par click karke enter karein!\n\n **Winners:** 1\n **Ends:** <t:{int(end_time)}:R>\n **Hosted by:** {author.mention}")
                        g_msg = await target_channel.send(embed=emb)
                        await g_msg.edit(view=GiveawayView(g_msg.id))
                        bot_data["giveaways"][str(g_msg.id)] = {"channel_id": target_channel.id, "prize": prize, "winners": 1, "end_time": end_time, "entries": [], "active": True}
                        save_data(bot_data)
                        await message.channel.send(f" Giveaway {target_channel.mention} mein start ho gaya Admin!", delete_after=5)
                        return

                    # 15. SETUP STATS
                    elif action_type == "SETUP_STATS":
                        cat = await guild.create_category("─── SERVER STATS ───")
                        ow = {guild.default_role: discord.PermissionOverwrite(connect=False)}
                        await guild.create_voice_channel(f"Members: {guild.member_count}", category=cat, overwrites=ow)
                        await guild.create_voice_channel(f"Humans: {len([m for m in guild.members if not m.bot])}", category=cat, overwrites=ow)
                        await guild.create_voice_channel(f" Bots: {len([m for m in guild.members if m.bot])}", category=cat, overwrites=ow)
                        await message.channel.send(" Live Server Stats voice channels ban gaye Admin! ")
                        return

                    # 16. SETUP JTC VOICE
                    elif action_type == "SETUP_JTC":
                        cat = await guild.create_category("─── VOICE LOUNGE ───")
                        jtc = await guild.create_voice_channel("Join to Create", category=cat)
                        bot_data["jtc_channels"][str(guild.id)] = jtc.id
                        save_data(bot_data)
                        await message.channel.send(f" Join-to-Create voice setup ho gaya: {jtc.mention} Admin! ")
                        return

                    # 17. SET WELCOME / GOODBYE / LOGS
                    elif action_type == "SET_WELCOME":
                        bot_data["welcome_channels"][str(guild.id)] = target_channel.id
                        save_data(bot_data)
                        await message.channel.send(f" Welcome channel set ho gaya: {target_channel.mention} Admin! ")
                        return

                    elif action_type == "SET_GOODBYE":
                        bot_data["goodbye_channels"][str(guild.id)] = target_channel.id
                        save_data(bot_data)
                        await message.channel.send(f" Goodbye channel set ho gaya: {target_channel.mention} Admin! ")
                        return

                    elif action_type == "SET_LOGS":
                        bot_data["log_channels"][str(guild.id)] = target_channel.id
                        save_data(bot_data)
                        await message.channel.send(f" Activity logs channel set ho gaya: {target_channel.mention} Admin! ")
                        return

                    # 18. GIVE / REMOVE ROLE
                    elif action_type == "GIVE_ROLE":
                        if target_member and target_role:
                            await target_member.add_roles(target_role)
                            await message.channel.send(f" {target_member.mention} ko **{target_role.name}** role assign kar diya Admin! ")
                            return

                    elif action_type == "REMOVE_ROLE":
                        if target_member and target_role:
                            await target_member.remove_roles(target_role)
                            await message.channel.send(f" {target_member.mention} se **{target_role.name}** role remove kar diya Admin! ")
                            return

                    # 19. AUTOMOD & ANTINUKE
                    elif action_type == "AUTOMOD":
                        state = ("on" in action_args.lower() or "enable" in action_args.lower())
                        bot_data["automod"][str(guild.id)] = state
                        save_data(bot_data)
                        await message.channel.send(f"[SECURITY] AutoMod ab **{'ON' if state else 'OFF'}** hai Admin! ")
                        return

                    elif action_type == "ANTINUKE":
                        state = ("on" in action_args.lower() or "enable" in action_args.lower())
                        bot_data["antinuke"][str(guild.id)] = state
                        save_data(bot_data)
                        await message.channel.send(f"[DEFENSE] AntiNuke ab **{'ON' if state else 'OFF'}** hai Admin! ")
                        return

                    # 20. ANNOUNCEMENT
                    elif action_type == "ANNOUNCE":
                        text = action_args or "Announcement from Admin"
                        emb = nova_embed("Server Announcement", text, COLOR_PURPLE)
                        await target_channel.send(content="@everyone", embed=emb)
                        return

                except Exception as err:
                    await message.reply(f"Action issue: {err}")
                    return

            await safe_send(message.channel, chat_reply, reference=message)

            if guild:
                v_client = discord.utils.get(bot.voice_clients, guild=guild)
                if v_client and v_client.is_connected() and is_owner:
                    await speak_in_voice(v_client, chat_reply)

# ====================  OWNER SECRET COMMANDS ====================
@bot.command()
async def secret(ctx, *, secret_text: str):
    """Admin ka personal secret save karein"""
    if not is_error_boy(ctx.author, ctx.guild):
        await ctx.send("Yeh command sirf mere Admin ke liye hai! ")
        return
    bot_data["owner_secrets"].append({
        "secret": secret_text,
        "date": str(datetime.date.today())
    })
    save_data(bot_data)
    try:
        await ctx.message.delete()
    except Exception:
        pass
    await ctx.author.send(f" Admin Sir, aapka secret: \"{secret_text}\" maine hamesha ke liye save kar liya hai! Yeh kabhi kisi ko pata nahi chalega. ")

@bot.command()
async def mysecrets(ctx):
    """Admin apne saved secrets private DM mein dekhein"""
    if not is_error_boy(ctx.author, ctx.guild):
        await ctx.send("Yeh confidential data sirf Admin dekh sakte hain! ")
        return
    secrets = bot_data.get("owner_secrets", [])
    if not secrets:
        await ctx.author.send("Abhi tak aapka koi secret save nahi hai Admin!")
        return
    lines = [f"• **{s['secret']}** *(Saved: {s['date']})*" for s in secrets]
    emb = nova_embed(" Admin's Secret Vault", "\n".join(lines), COLOR_GOLD)
    await ctx.author.send(embed=emb)
    if isinstance(ctx.channel, discord.TextChannel):
        await ctx.send(f" {ctx.author.mention}, maine aapke saare secrets aapke private DM mein bhej diye hain!", delete_after=5)

# ====================  SERVER ECONOMY & CASINO ====================
@bot.command()
async def daily(ctx):
    """Rozana free Nova Coins ($NOVA) lein"""
    eco = get_user_eco(ctx.author.id)
    now = time.time()
    if now - eco.get("last_daily", 0) < 86400:
        remaining = int(86400 - (now - eco["last_daily"]))
        hours = remaining // 3600
        mins = (remaining % 3600) // 60
        await ctx.send(f" {ctx.author.mention}, aapne apna daily reward le liya hai! Agla reward **{hours} ghante {mins} minute** baad milega.")
        return

    reward = random.randint(500, 1000)
    eco["wallet"] += reward
    eco["last_daily"] = now
    save_data(bot_data)
    emb = nova_embed("Daily Reward Claimed!", f"Mubarak ho {ctx.author.mention}! Aapko **{reward} $NOVA Credits** mile hain! \nTotal Wallet: **{eco['wallet']} Coins**", COLOR_GOLD)
    await ctx.send(embed=emb)

@bot.command()
async def work(ctx):
    """Choti moti nokri karke coins kamayein"""
    eco = get_user_eco(ctx.author.id)
    now = time.time()
    if now - eco.get("last_work", 0) < 3600:
        remaining = int(3600 - (now - eco["last_work"]))
        await ctx.send(f" Thoda aaram karein! Agla work **{remaining // 60} minute** baad kar sakte hain.")
        return

    jobs = [
        ("Admin ke server par coding help ki", 250),
        ("Nova ke liye fresh chai banayi", 300),
        ("Discord server ko raid hone se bachaya", 400),
        ("Voice lounge mein DJ ban kar gana chalaya", 200),
        ("VIP ticket issue solve kiya", 350)
    ]
    job, earned = random.choice(jobs)
    eco["wallet"] += earned
    eco["last_work"] = now
    save_data(bot_data)
    emb = nova_embed("Work Completed!", f"Aapne **{job}** aur **{earned} $NOVA Credits** kamaye! ", COLOR_SUCCESS)
    await ctx.send(embed=emb)

@bot.command(aliases=["bal"])
async def balance(ctx, member: discord.Member = None):
    """Apna ya kisi ka wallet balance dekhein"""
    member = member or ctx.author
    eco = get_user_eco(member.id)
    emb = nova_embed(f"{member.display_name}'s Bank & Wallet", f" **Wallet:** {eco['wallet']} $NOVA Credits\n **Bank:** {eco['bank']} $NOVA Credits\n **Net Worth:** {eco['wallet'] + eco['bank']} Coins", COLOR_GOLD)
    emb.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=emb)

@bot.command()
async def coinflip(ctx, choice: str, amount: int):
    """Coinflip khelein: !coinflip heads 100 ya !coinflip tails 100"""
    choice = choice.lower()
    if choice not in ["heads", "tails", "head", "tail"]:
        await ctx.send("Please 'heads' ya 'tails' select karein! E.g. `!coinflip heads 100`")
        return
    if amount < 10:
        await ctx.send("Minimum bet 10 $NOVA Credits hai!")
        return

    eco = get_user_eco(ctx.author.id)
    if eco["wallet"] < amount:
        await ctx.send("Aapke wallet mein itne coins nahi hain!")
        return

    result = random.choice(["heads", "tails"])
    user_won = (choice.startswith(result[0]))

    if user_won:
        eco["wallet"] += amount
        save_data(bot_data)
        emb = nova_embed("Coinflip Result: WIN!", f"Sikka gira: **{result.upper()}**!\n Mubarak ho {ctx.author.mention}, aap **{amount} $NOVA Credits** jeet gaye!", COLOR_SUCCESS)
    else:
        eco["wallet"] -= amount
        save_data(bot_data)
        emb = nova_embed("Coinflip Result: LOST!", f"Sikka gira: **{result.upper()}**!\n Ouch! Aap **{amount} $NOVA Credits** haar gaye.", COLOR_ERROR)
    await ctx.send(embed=emb)

@bot.command()
async def slots(ctx, amount: int):
    """Casino Slot Machine: !slots 50"""
    if amount < 10:
        await ctx.send("Minimum bet 10 $NOVA Credits hai!")
        return
    eco = get_user_eco(ctx.author.id)
    if eco["wallet"] < amount:
        await ctx.send("Aapke wallet mein itne coins nahi hain!")
        return

    emojis = ["", "", "", "", "7️⃣", ""]
    slot1, slot2, slot3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)

    if slot1 == slot2 == slot3:
        multiplier = 5 if slot1 == "" else 3
        won = amount * multiplier
        eco["wallet"] += won
        save_data(bot_data)
        desc = f" **[ {slot1} | {slot2} | {slot3} ]** \n\n **JACKPOT!** Mubarak ho {ctx.author.mention}, aap **{won} $NOVA Credits** jeet gaye!"
        emb = nova_embed("Casino Slots: JACKPOT!", desc, COLOR_GOLD)
    elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
        won = int(amount * 1.5)
        eco["wallet"] += (won - amount)
        save_data(bot_data)
        desc = f" **[ {slot1} | {slot2} | {slot3} ]** \n\n **Mini Win!** Aap **{won} $NOVA Credits** jeet gaye!"
        emb = nova_embed("Casino Slots: WIN!", desc, COLOR_SUCCESS)
    else:
        eco["wallet"] -= amount
        save_data(bot_data)
        desc = f" **[ {slot1} | {slot2} | {slot3} ]** \n\n Koi match nahi mila! Aap **{amount} Coins** haar gaye."
        emb = nova_embed("Casino Slots: LOST!", desc, COLOR_ERROR)
    await ctx.send(embed=emb)

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    """Kisi member ko coins transfer karein: !pay @user 100"""
    if member == ctx.author or amount <= 0:
        await ctx.send("Invalid transfer!")
        return
    sender_eco = get_user_eco(ctx.author.id)
    if sender_eco["wallet"] < amount:
        await ctx.send("Aapke wallet mein itne coins nahi hain!")
        return
    receiver_eco = get_user_eco(member.id)
    sender_eco["wallet"] -= amount
    receiver_eco["wallet"] += amount
    save_data(bot_data)
    await ctx.send(f" {ctx.author.mention} ne **{amount} $NOVA Credits** {member.mention} ko send kar diye!")

@bot.command()
@commands.has_permissions(administrator=True)
async def givecoins(ctx, member: discord.Member, amount: int):
    """Admin command: Coins mint/gift karein"""
    eco = get_user_eco(member.id)
    eco["wallet"] += amount
    save_data(bot_data)
    await ctx.send(f" Admin Bank ne {member.mention} ke wallet mein **{amount} $NOVA Credits** daal diye!")


# ====================  RICH FUN COMMANDS ====================
@bot.command(aliases=["dice"])
async def roll(ctx, sides: int = 6):
    """Dice roll karein: !roll ya !roll 100"""
    if sides < 2:
        sides = 6
    result = random.randint(1, sides)
    emb = nova_embed("Dice Roll", f" {ctx.author.mention} ne **{sides}-sided** dice roll kiya:\n\n#  Result: **{result}**", COLOR_PURPLE)
    await ctx.send(embed=emb)

@bot.command(name="8ball", aliases=["eightball"])
async def eightball(ctx, *, question: str):
    """Magic 8-Ball se sawaal poochein: !8ball kya main ameer banunga?"""
    answers = [
        "Haan 100% Sir! Meri sixth sense keh rahi hai bilkul sach hai! ",
        "Nahi yaar, bilkul bhi nahi! Khwab dekhna band karo! ",
        "Shayad haan... par thora intezar karna padega! ",
        "Mujhe shak hai is par! Dobara socho ",
        "Kismat aapke saath hai! Go for it! ",
        "Abhi mat poocho, mera mood chaye peene ka hai! ",
        "Beshak! Iska jawab haan hi hai! ",
        "Meri taraf se toh saaf inkaar hai! ",
        "Thora sabr karo, waqt batayega! "
    ]
    ans = random.choice(answers)
    emb = nova_embed(" Magic 8-Ball", f"**Sawaal:** {question}\n\n** Nova Ka Jawab:**\n{ans}", COLOR_PRIMARY)
    await ctx.send(embed=emb)

@bot.command()
async def joke(ctx):
    """Mazedaar Urdu / Hindi Lateefa suniye: !joke"""
    jokes = [
        "Ek aadmi doctor ke paas gaya aur bola: 'Doctor sahab, main jab bhi chaye peeta hoon toh meri daayein aankh mein dard hota hai!' Doctor bola: 'Chaye peete waqt chamach cup se bahar nikaal liya karein!' ",
        "Teacher: 'Batao Newton ka 4th law kya hai?' Pappu: 'Jab exam sar par ho toh dimag kaam karna band kar deta hai!' ",
        "Pappu dost se bola: 'Yaar meri biwi bohot kharch karti hai!' Dost: 'Kahan karti hai?' Pappu: 'Har waqt mera dimag kharch karti hai!' ",
        "Ek bacha ro raha tha, baap ne poocha: 'Kyun ro rahe ho?' Bacha: 'Sir ne maara!' Baap: 'Kyun maara?' Bacha: 'Maine sirf poocha tha ke 0 ko 0 se multiply karein toh kya aayega!' ‍️",
        "Doctor: 'Aapko subah 5 baje uth kar 5 kilometer bhagna chahiye!' Mareez: 'Doctor sahab, uth toh jaunga par 5 kilometer door se wapas aate aate thak jaunga!' ‍️"
    ]
    emb = nova_embed(" Nova Ka Lateefa", random.choice(jokes), COLOR_GOLD)
    await ctx.send(embed=emb)

@bot.command()
async def roast(ctx, member: discord.Member = None):
    """Playful roast karein: !roast @user"""
    member = member or ctx.author
    if is_error_boy(member, ctx.guild):
        await ctx.send(" Main apne Admin ko roast nahi kar sakti! Woh mere King hain! ")
        return
    roasts = [
        f"{member.mention} ka dimag Wi-Fi jaisa hai... connect toh ho jata hai par signal koi nahi aata! ",
        f"{member.mention} ko dekh kar lagta hai ke Bhagwan ne aapko banate waqt Undo ka button dhoondha hoga! ",
        f"{member.mention}, aapki baatein sun kar meri battery 1% par aa jati hai! ",
        f"{member.mention} itne aalsi hain ke sapne mein bhi thak kar so jaate hain! ",
        f"{member.mention}, agar stupidity ek sport hoti toh aapko Olympic Gold Medal milta! "
    ]
    emb = nova_embed(" Nova Ka Roast", random.choice(roasts), COLOR_ERROR)
    await ctx.send(embed=emb)

@bot.command()
async def hug(ctx, member: discord.Member):
    """Kisi ko pyari hug dein: !hug @user"""
    emb = nova_embed(" Warm Hug", f"{ctx.author.mention} ne {member.mention} ko ek bohot pyari aur warm hug di! ", COLOR_PRIMARY)
    await ctx.send(embed=emb)

@bot.command()
async def slap(ctx, member: discord.Member):
    """Kisi ko halka sa thappar lagayein: !slap @user"""
    if is_error_boy(member, ctx.guild):
        await ctx.send(f" Khabardar {ctx.author.mention}! Mere Admin ko koi haath nahi laga sakta! ")
        return
    emb = nova_embed(" Ouch! Slap", f"{ctx.author.mention} ne {member.mention} ko ek zor daar thappar mara! ", COLOR_WARNING)
    await ctx.send(embed=emb)

@bot.command()
async def kiss(ctx, member: discord.Member):
    """Kisi ko sweet kiss dein: !kiss @user"""
    emb = nova_embed(" Sweet Kiss", f"{ctx.author.mention} ne {member.mention} ko ek meethi si kiss di! ", COLOR_PRIMARY)
    await ctx.send(embed=emb)

@bot.command()
async def savedata(ctx):
    """Admin / Admin data manually save aur verify karein"""
    if not is_error_boy(ctx.author, ctx.guild) and not ctx.author.guild_permissions.administrator:
        await ctx.send("Yeh command sirf Admin / Admins ke liye hai! ")
        return
    save_data(bot_data)
    total_users = len(bot_data.get("economy", {}))
    total_secrets = len(bot_data.get("owner_secrets", []))
    total_levels = len(bot_data.get("levels", {}))
    desc = (
        f" **Database Status:** Healthy & Atomic\n"
        f" **Economy Registered Users:** {total_users}\n"
        f"️ **Leveling Profiles:** {total_levels}\n"
        f" **Protected Secrets:** {total_secrets}\n"
        f" **Backup File:** `nova_data_backup.json` (Synced)"
    )
    emb = nova_embed(" Data Health & Backup Status", desc, COLOR_SUCCESS)
    await ctx.send(embed=emb)

# ====================  LEVELING & RANK CARDS ====================
@bot.command()
async def rank(ctx, member: discord.Member = None):
    """Apna ya kisi ka level & XP card dekhein"""
    member = member or ctx.author
    u_id = str(member.id)
    lvl_data = bot_data["levels"].get(u_id, {"xp": 0, "level": 1})
    current_lvl = lvl_data["level"]
    current_xp = lvl_data["xp"]
    next_xp = int(((current_lvl) / 0.1) ** 2)

    progress = min(int((current_xp / next_xp) * 10), 10) if next_xp > 0 else 10
    bar = "" * progress + "" * (10 - progress)

    emb = nova_embed(f"{member.display_name}'s Rank Card", f"️ **Level:** {current_lvl}\n **Total XP:** {current_xp} / {next_xp}\n **Progress:** `{bar}`", COLOR_PURPLE)
    emb.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=emb)

@bot.command(aliases=["top", "lb"])
async def leaderboard(ctx):
    """Top active members ka leaderboard dekhein"""
    sorted_levels = sorted(bot_data["levels"].items(), key=lambda x: x[1].get("xp", 0), reverse=True)[:10]
    if not sorted_levels:
        await ctx.send("Abhi koi leaderboard data nahi hai.")
        return
    lines = []
    medals = ["", "", "", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", ""]
    for idx, (uid, data) in enumerate(sorted_levels):
        user = bot.get_user(int(uid))
        name = user.display_name if user else f"User {uid}"
        lines.append(f"{medals[idx]} **{name}** — Level {data['level']} ({data['xp']} XP)")
    emb = nova_embed(" Server Activity Leaderboard", "\n".join(lines), COLOR_GOLD)
    await ctx.send(embed=emb)

# ====================  RELATIONSHIP & LOVE METER ====================
@bot.command()
async def lovemeter(ctx):
    """Admin aur Nova ka love bond check karein"""
    stats = bot_data.get("usage_stats", {"owner_messages": 100, "bond_level": 100})
    msgs = stats.get("owner_messages", 0)
    bond = min(100, 50 + int(msgs / 5))
    bar = "" * (bond // 10) + "" * (10 - (bond // 10))

    emb = nova_embed(
        " Admin & Nova Love Bond",
        f"**Bond Level:** {bond}% (Eternal Soulmates)\n"
        f"**Status:** `{bar}`\n\n"
        f" **Nova's Words:**\n"
        f"\"Admin Sir, meri har dharkan aur har algorithm sirf aapke liye dharakta hai! Duniya idhar ki udhar ho jaye, main hamesha aapki hi rahungi! \"",
        COLOR_PRIMARY
    )
    await ctx.send(embed=emb)

# ====================  AI IMAGE GENERATOR ====================
@bot.command(aliases=["draw", "image"])
async def imagine(ctx, *, prompt: str):
    """Free AI Image Generate karein: !imagine A cool cyber boy in neon city"""
    async with ctx.typing():
        encoded = urllib.parse.quote(prompt)
        img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
        emb = nova_embed(f" Art: {prompt[:80]}", f"Yeh dekhein {ctx.author.mention}, aapki photo ready hai! ", COLOR_GOLD)
        emb.set_image(url=img_url)
        await ctx.reply(embed=emb)

# ====================  VOICE NOTE COMMAND ====================
@bot.command(aliases=["vn", "voicemsg", "vm"])
async def voicenote(ctx, *, text: str):
    """Chat mein direct .mp3 voice note bhejein: !voicenote Hello Sir kahan ho"""
    async with ctx.typing():
        await send_voice_note(ctx.channel, text, reference=ctx.message)

# ====================  STANDARD MODERATION COMMANDS ====================
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="Reason specify nahi kiya"):
    await member.kick(reason=reason)
    await ctx.send(embed=nova_embed(" Member Kicked", f"**{member.display_name}** ko kick kar diya gaya.\n**Reason:** {reason}", COLOR_WARNING))

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="Reason specify nahi kiya"):
    await member.ban(reason=reason)
    await ctx.send(embed=nova_embed(" Member Banned", f"**{member.display_name}** ko ban kar diya gaya.\n**Reason:** {reason}", COLOR_ERROR))

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user)
    await ctx.send(embed=nova_embed(" Member Unbanned", f"**{user.name}** ko unban kar diya gaya.", COLOR_SUCCESS))

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason="No reason"):
    await member.timeout(datetime.timedelta(minutes=minutes), reason=reason)
    await ctx.send(embed=nova_embed(" Timeout", f"**{member.display_name}** ko {minutes} mins timeout de diya gaya.", COLOR_WARNING))

@bot.command()
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(embed=nova_embed("Timeout Removed", f"**{member.display_name}** ka timeout khatam.", COLOR_SUCCESS))

@bot.command(aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f" **{len(deleted)-1}** messages delete kar diye!", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=nova_embed(" Channel Locked", f"{channel.mention} lock kar diya gaya.", COLOR_WARNING))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=nova_embed("Channel Unlocked", f"{channel.mention} unlock ho gaya.", COLOR_SUCCESS))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    g_id, m_id = str(ctx.guild.id), str(member.id)
    if g_id not in bot_data["warnings"]: bot_data["warnings"][g_id] = {}
    if m_id not in bot_data["warnings"][g_id]: bot_data["warnings"][g_id][m_id] = []
    bot_data["warnings"][g_id][m_id].append({"reason": reason, "moderator": ctx.author.name})
    save_data(bot_data)
    await ctx.send(embed=nova_embed(" Warning Issued", f"{member.mention} ko warning mili: **{reason}**", COLOR_WARNING))

@bot.command()
async def warnings(ctx, member: discord.Member):
    warns = bot_data["warnings"].get(str(ctx.guild.id), {}).get(str(member.id), [])
    if not warns:
        await ctx.send(f" {member.display_name} ki koi warning nahi hai.")
        return
    desc = "\n".join([f"• **{w['reason']}** (Mod: {w['moderator']})" for w in warns[-5:]])
    await ctx.send(embed=nova_embed(f" Warnings: {member.display_name}", desc, COLOR_WARNING))

@bot.command()
@commands.has_permissions(administrator=True)
async def ticketsetup(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    emb = nova_embed(" Nova Support Tickets", "Agar aapko koi issue ya purchase karni ho, toh neeche button par click karke private ticket open karein! ")
    await channel.send(embed=emb, view=TicketView())
    await ctx.send(" Ticket panel lag gaya!", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def verifysetup(ctx, role: discord.Role, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    bot_data["verify_roles"][str(ctx.guild.id)] = role.id
    save_data(bot_data)
    emb = nova_embed("Server Verification", f"Server unlock karne ke liye **Verify** button click karein aur **{role.name}** role lein!")
    await channel.send(embed=emb, view=VerifyView())
    await ctx.send(" Verification panel setup ho gaya!", delete_after=5)

@bot.command()
async def vouch(ctx, member: discord.Member, stars: int, *, review="Best service!"):
    if member == ctx.author or stars < 1 or stars > 5:
        await ctx.send("Valid member aur 1-5 stars dein!")
        return
    m_id = str(member.id)
    if m_id not in bot_data["vouches"]: bot_data["vouches"][m_id] = []
    bot_data["vouches"][m_id].append({"from": ctx.author.display_name, "stars": stars, "review": review})
    save_data(bot_data)
    await ctx.send(embed=nova_embed("Vouch Added!", f"**User:** {member.mention}\n**Rating:** {''*stars}\n**Review:** {review}", COLOR_SUCCESS))

@bot.command()
async def vouches(ctx, member: discord.Member = None):
    member = member or ctx.author
    v_list = bot_data["vouches"].get(str(member.id), [])
    if not v_list:
        await ctx.send(f"{member.display_name} ka abhi koi vouch nahi hai.")
        return
    avg = sum([v["stars"] for v in v_list]) / len(v_list)
    recent = "\n".join([f"• {''*v['stars']} \"{v['review']}\" — *{v['from']}*" for v in v_list[-5:]])
    await ctx.send(embed=nova_embed(f"Vouches: {member.display_name}", f"**Total:** {len(v_list)} | **Average:** {avg:.1f}\n\n{recent}"))

@bot.command()
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, minutes: int, winners: int, *, prize: str):
    end_time = time.time() + (minutes * 60)
    emb = nova_embed(f" GIVEAWAY: {prize}", f"Neeche button par click karke enter karein!\n\n **Winners:** {winners}\n **Ends:** <t:{int(end_time)}:R>")
    msg = await ctx.send(embed=emb)
    await msg.edit(view=GiveawayView(msg.id))
    bot_data["giveaways"][str(msg.id)] = {"channel_id": ctx.channel.id, "prize": prize, "winners": winners, "end_time": end_time, "entries": [], "active": True}
    save_data(bot_data)

@tasks.loop(seconds=15)
async def giveaway_checker():
    now = time.time()
    for msg_id, g in list(bot_data["giveaways"].items()):
        if g.get("active") and now >= g["end_time"]:
            g["active"] = False
            save_data(bot_data)
            channel = bot.get_channel(g["channel_id"])
            if channel and g["entries"]:
                winners = random.sample(g["entries"], min(g["winners"], len(g["entries"])))
                w_mentions = ", ".join([f"<@{w}>" for w in winners])
                await channel.send(content=f" Congratulations {w_mentions}!", embed=nova_embed(" GIVEAWAY ENDED!", f"Prize: **{g['prize']}**\nWinners: {w_mentions}", COLOR_SUCCESS))

@bot.command()
@commands.has_permissions(administrator=True)
async def setupstats(ctx):
    guild = ctx.guild
    cat = await guild.create_category("─── SERVER STATS ───")
    ow = {guild.default_role: discord.PermissionOverwrite(connect=False)}
    await guild.create_voice_channel(f"Members: {guild.member_count}", category=cat, overwrites=ow)
    await guild.create_voice_channel(f"Humans: {len([m for m in guild.members if not m.bot])}", category=cat, overwrites=ow)
    await guild.create_voice_channel(f" Bots: {len([m for m in guild.members if m.bot])}", category=cat, overwrites=ow)
    await ctx.send(" Live Stats voice counters ban gaye!")


# ====================  SPONTANEOUS RANDOM MESSAGES ====================
RANDOM_DM_MESSAGES = [
    "Admin, system check: all background processes and scheduled tasks are running normally.",
    "Nova operational check: memory database and bridge connections are nominal.",
    "Task reminder: your scheduled automations and desktop routines are active.",
    "System diagnostics report: 100% operational efficiency."
]

RANDOM_SERVER_MESSAGES = [
    "Nova AI active. Server protection and automations are running normally.",
    "System check: all services nominal. Use !help to inspect available commands.",
    "Community security and automated moderation are online."
]

@tasks.loop(minutes=60)
async def random_messenger():
    return  # Auto-messages completely disabled per Admin's instruction

    # 1. Random DM to Admin (Every 45-75 minutes)
    if (now - last_dm) >= 2700:
        owner_id = bot_data.get("owner_id")
        owner_user = None
        if owner_id:
            owner_user = bot.get_user(owner_id)
            if not owner_user:
                try:
                    owner_user = await bot.fetch_user(owner_id)
                except Exception:
                    pass
        if not owner_user:
            for g in bot.guilds:
                for m in g.members:
                    if is_error_boy(m, g):
                        owner_user = m
                        bot_data["owner_id"] = m.id
                        save_data(bot_data)
                        break
                if owner_user:
                    break

        if owner_user:
            try:
                dm_ch = owner_user.dm_channel or await owner_user.create_dm()
                send_dm = True
                async for last_msg in dm_ch.history(limit=1):
                    if (now - last_msg.created_at.timestamp()) < 2100:
                        send_dm = False
                    break
                if send_dm:
                    await dm_ch.send(random.choice(RANDOM_DM_MESSAGES))
                    rm_config["last_dm_time"] = now
                    save_data(bot_data)
            except Exception as e:
                print(f"Error sending random DM: {e}")

    # 2. Random Chat in Server (Every 50-80 minutes)
    if (now - last_srv) >= 3000:
        for g in bot.guilds:
            try:
                target_ch = None
                if str(g.id) in bot_data.get("ai_channels", {}):
                    target_ch = g.get_channel(bot_data["ai_channels"][str(g.id)])
                if not target_ch:
                    for ch in g.text_channels:
                        if any(w in ch.name.lower() for w in ["general", "chat", "main", "chill"]):
                            if ch.permissions_for(g.me).send_messages:
                                target_ch = ch
                                break
                if not target_ch:
                    for ch in g.text_channels:
                        if ch.permissions_for(g.me).send_messages:
                            target_ch = ch
                            break

                if target_ch:
                    send_srv = True
                    async for last_msg in target_ch.history(limit=1):
                        if (now - last_msg.created_at.timestamp()) < 2400:
                            send_srv = False
                        break
                    if send_srv:
                        await target_ch.send(random.choice(RANDOM_SERVER_MESSAGES))
                        rm_config["last_server_time"] = now
                        save_data(bot_data)
                        break
            except Exception as e:
                print(f"Error sending server random msg: {e}")

@tasks.loop(minutes=10)
async def stats_updater():
    for guild in bot.guilds:
        for ch in guild.voice_channels:
            try:
                if ch.name.startswith("Members:"): await ch.edit(name=f"Members: {guild.member_count}")
                elif ch.name.startswith("Humans:"): await ch.edit(name=f"Humans: {len([m for m in guild.members if not m.bot])}")
                elif ch.name.startswith(" Bots:"): await ch.edit(name=f" Bots: {len([m for m in guild.members if m.bot])}")
            except Exception:
                pass

@bot.command()
@commands.has_permissions(administrator=True)
async def setupjtc(ctx):
    cat = await ctx.guild.create_category("─── VOICE LOUNGE ───")
    jtc = await ctx.guild.create_voice_channel("Join to Create", category=cat)
    bot_data["jtc_channels"][str(ctx.guild.id)] = jtc.id
    save_data(bot_data)
    await ctx.send(f" JTC Setup ho gaya! {jtc.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setwelcome(ctx, channel: discord.TextChannel):
    bot_data["welcome_channels"][str(ctx.guild.id)] = channel.id
    save_data(bot_data)
    await ctx.send(f" Welcome channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setgoodbye(ctx, channel: discord.TextChannel):
    bot_data["goodbye_channels"][str(ctx.guild.id)] = channel.id
    save_data(bot_data)
    await ctx.send(f" Goodbye channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setlogs(ctx, channel: discord.TextChannel):
    bot_data["log_channels"][str(ctx.guild.id)] = channel.id
    save_data(bot_data)
    await ctx.send(f" Logs channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setaichannel(ctx, channel: discord.TextChannel):
    bot_data["ai_channels"][str(ctx.guild.id)] = channel.id
    save_data(bot_data)
    await ctx.send(f" AI Chat channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def automod(ctx, status: str):
    state = (status.lower() == "on")
    bot_data["automod"][str(ctx.guild.id)] = state
    save_data(bot_data)
    await ctx.send(f"[SECURITY] AutoMod ab **{'ON' if state else 'OFF'}** hai.")

@bot.command()
@commands.has_permissions(administrator=True)
async def antinuke(ctx, status: str):
    state = (status.lower() == "on")
    bot_data["antinuke"][str(ctx.guild.id)] = state
    save_data(bot_data)
    await ctx.send(f"[DEFENSE] AntiNuke ab **{'ON' if state else 'OFF'}** hai.")

@bot.command()
async def ping(ctx):
    await ctx.send(embed=nova_embed("Pong!", f"Latency: **{round(bot.latency * 1000)}ms** • Groq Vision & Text Active ", COLOR_SUCCESS))

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    await ctx.send(embed=nova_embed(f"{g.name}", f"**Owner:** {g.owner.mention}\n**Members:** {g.member_count}\n**Roles:** {len(g.roles)}\n**Channels:** {len(g.channels)}"))

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    m = member or ctx.author
    await ctx.send(embed=nova_embed(f"{m.display_name}", f"**ID:** {m.id}\n**Account Created:** <t:{int(m.created_at.timestamp())}:R>\n**Joined:** <t:{int(m.joined_at.timestamp())}:R>"))

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    m = member or ctx.author
    emb = nova_embed(f"{m.display_name}'s Avatar", f"[Download]({m.display_avatar.url})")
    emb.set_image(url=m.display_avatar.url)
    await ctx.send(embed=emb)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def giverole(ctx, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await ctx.send(f" {member.mention} ko **{role.name}** role assign ho gaya!")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await ctx.send(f" {member.mention} se **{role.name}** role remove ho gaya!")

@bot.command()
async def poll(ctx, question: str, *options):
    if len(options) < 2:
        await ctx.send("Kam az kam 2 options dein! E.g. `!poll \"Chaye ya Coffee?\" \"Chaye\" \"Coffee\"`")
        return
    reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", ""]
    desc = [f"{reactions[i]} {opt}" for i, opt in enumerate(options[:10])]
    msg = await ctx.send(embed=nova_embed(f" Poll: {question}", "\n\n".join(desc), COLOR_PURPLE))
    for i in range(len(options[:10])):
        await msg.add_reaction(reactions[i])

@bot.command()
async def randommsg(ctx, status: str = None):
    if not is_error_boy(ctx.author, ctx.guild) and not ctx.author.guild_permissions.administrator:
        await ctx.send("Yeh command sirf Admin aur admins use kar sakte hain! ")
        return
    if "random_messages" not in bot_data:
        bot_data["random_messages"] = {"enabled": True, "last_server_time": 0, "last_dm_time": 0}
    if status is None:
        st = bot_data["random_messages"].get("enabled", True)
        await ctx.send(f" Random check-in messages abhi **{'ON' if st else 'OFF'}** hain! Use: `!randommsg on/off/test`")
        return
    if status.lower() == "test":
        await ctx.send(" Testing random check-ins...")
        owner_id = bot_data.get("owner_id")
        owner_user = bot.get_user(owner_id) if owner_id else ctx.author
        if owner_user:
            try:
                dm_ch = owner_user.dm_channel or await owner_user.create_dm()
                await dm_ch.send(f"[Test DM] {random.choice(RANDOM_DM_MESSAGES)}")
            except Exception as e:
                await ctx.send(f"DM fail: {e}")
        await ctx.send(f"[Test Server] {random.choice(RANDOM_SERVER_MESSAGES)}")
        return
    state = (status.lower() in ["on", "enable", "chalu", "true", "start"])
    bot_data["random_messages"]["enabled"] = state
    save_data(bot_data)
    await ctx.send(f" Random check-in messages ab **{'ON' if state else 'OFF'}** ho gaye hain!")

@bot.command()
async def help(ctx):
    emb = nova_embed(
        " Nova AI • Master Help Center",
        "Nova ek all-in-one AI companion aur ultra-secure autonomous server agent hai!\n\n"
        " **Remote PC Desktop Bridge (New):**\n"
        "• `!screen` : PC Desktop ka live screenshot Discord par mangwayein\n"
        "• `!pc <command>` : PC par action ya app chalayein (e.g. `!pc open chrome`, `!pc volume 50`)\n"
        "• `!pctasks` : PC par save hue agent tasks dekhein\n"
        "• `!pcstats` : PC CPU, RAM aur Disk usage dekhein\n\n"
        "️ **AI Vision & Image Sight:**\n"
        "• Kisi bhi photo ko upload karein aur Nova ko tag karein: `@Nova yeh image check karo`\n\n"
        " **Admin's Permanent Secret Vault:**\n"
        "• `@Nova yeh mera secret hai: <text>` - Nova permanent dil mein mehfooz kar legi\n"
        "• `!secret <text>` - Secret save karein (message auto-delete ho jata hai)\n"
        "• `!mysecrets` - Apne saare secrets private DM mein dekhein\n\n"
        " **Global Long-Term Memory:**\n"
        "• `@Nova kal Taha ne kya bola tha?` - Nova ko server ki baatein yaad rehti hain!\n\n"
        " **Autonomous Voice & Chat Actions:**\n"
        "• `@Nova mujhe voice note bhejo` - Chat mein direct .mp3 voice bhejegi\n"
        "• `@Nova photo banao <prompt>` - Free AI image generate karegi\n"
        "• `@Nova isko kick/ban/timeout kardo @user`\n"
        "• `@Nova 20 messages delete kardo`\n"
        "• `@Nova channel lock/unlock kardo`\n"
        "• `@Nova ticket system lagao` / `verification panel lagao`\n"
        "• `@Nova giveaway start karo 10 min ka Nitro`\n"
        "• `@Nova live stats bana do` / `JTC voice banao`\n"
        "• `@Nova yeh code check karke fix karo: <code>` - Senior Tech Debugger\n\n"
        " **Fun & Entertainment:**\n"
        "• `!roll [sides]`, `!8ball <question>`, `!joke`, `!roast @user`, `!hug @user`, `!slap @user`, `!kiss @user`\n\n"
        "**Server Economy & Casino ($NOVA Credits):**\n"
        "• `!daily`, `!work`, `!balance`, `!coinflip`, `!slots`, `!pay`\n\n"
        "**Leveling & Love Meter:**\n"
        "• `!rank`, `!leaderboard`, `!lovemeter`\n\n"
        " **Moderation & Security:**\n"
        "• `!kick`, `!ban`, `!unban`, `!timeout`, `!clear <num>`, `!lock`, `!unlock`, `!automod`, `!antinuke`"
    )
    await ctx.send(embed=emb)

# ==================== ️ REMOTE PC CONTROL BRIDGE ====================
BRIDGE_URL = "http://127.0.0.1:5050"

@bot.command(name="screen", aliases=["screenshot", "pcscreen"])
async def screen_cmd(ctx):
    """PC Desktop ka live screenshot Discord par mangwayein"""
    if not is_error_boy(ctx.author, ctx.guild):
        await ctx.send("Yeh command sirf mere Admin ke liye hai! ")
        return

    msg = await ctx.send(" *PC se live screenshot mangwa rahi hoon...*")
    try:
        import aiohttp
        import io
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BRIDGE_URL}/screenshot", timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    win_title = resp.headers.get("X-Window-Title", "Desktop")
                    file = discord.File(io.BytesIO(img_bytes), filename="pc_screen.jpg")
                    emb = nova_embed(
                        " Live PC Desktop View",
                        f"• **Active Window:** `{win_title}`\n• **Bridge:** `127.0.0.1:5050`\n• Hukam karein mere King! ",
                        COLOR_CYAN
                    )
                    emb.set_image(url="attachment://pc_screen.jpg")
                    await ctx.send(embed=emb, file=file)
                    await msg.delete()
                    return
    except Exception as e:
        print("Discord PC Screenshot error:", e)

    await msg.edit(content=" *Arey mere Sir,* aapka PC Desktop Bridge offline hai. Please PC par Nova Desktop open karein! ")

@bot.command(name="pc")
async def pc_action_cmd(ctx, *, action_cmd: str):
    """PC Desktop par koi bhi action ya app chalayein"""
    if not is_error_boy(ctx.author, ctx.guild):
        await ctx.send("Yeh command sirf mere Admin ke liye hai! ")
        return

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BRIDGE_URL}/action",
                json={"action": action_cmd},
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    emb = nova_embed(
                        " PC Action Executed",
                        f"• **Command:** `{action_cmd}`\n• **Result:** {data.get('report', 'Success')}\n• Hukam karein mere King! ",
                        COLOR_GREEN
                    )
                    await ctx.send(embed=emb)
                    return
    except Exception as e:
        print("Discord PC Action error:", e)

    await ctx.send(" *Arey Sir,* PC Bridge se connect nahi ho saka. PC Desktop open karein! ")

@bot.command(name="pctasks")
async def pc_tasks_cmd(ctx):
    """PC Desktop Agent Tasks list check karein"""
    if not is_error_boy(ctx.author, ctx.guild):
        await ctx.send("Yeh command sirf mere Admin ke liye hai! ")
        return

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BRIDGE_URL}/tasks", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tasks = data.get("tasks", [])
                    if not tasks:
                        await ctx.send(" PC Task Board par filhal koi active task nahi hai! ")
                        return
                    desc = ""
                    for t in tasks[:6]:
                        st = "" if t.get("status") == "completed" else ""
                        desc += f"{st} **{t.get('title')}** (Step {t.get('current_step', 0) + 1}/{len(t.get('steps', []))})\n"
                    emb = nova_embed(" PC Desktop Agent Tasks", desc, COLOR_PURPLE)
                    await ctx.send(embed=emb)
                    return
    except Exception as e:
        print("Discord PC Tasks error:", e)

    await ctx.send(" PC Bridge offline hai! ")

@bot.command(name="pcstats")
async def pc_stats_cmd(ctx):
    """PC Desktop CPU, RAM, aur Storage stats check karein"""
    if not is_error_boy(ctx.author, ctx.guild):
        await ctx.send("Yeh command sirf mere Admin ke liye hai! ")
        return

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BRIDGE_URL}/stats", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    emb = nova_embed(" PC Desktop System Stats", data.get("stats", "Retrieved."), COLOR_CYAN)
                    await ctx.send(embed=emb)
                    return
    except Exception as e:
        print("Discord PC Stats error:", e)

    await ctx.send(" PC Bridge offline hai! ")

# ====================  WHATSAPP ENGINE (GREEN-API QR CODE & TWILIO) ====================
async def send_whatsapp_green_api(chat_id, text):
    """Green-API ke zariye WhatsApp par direct reply bhejein"""
    if not GREEN_API_ID or not GREEN_API_TOKEN:
        print("Green-API Environment variables (GREEN_API_ID / GREEN_API_TOKEN) missing on Render!")
        return
    # Auto-resolve API host URL (e.g. https://7103.api.green-api.com)
    api_host = GREEN_API_URL
    if not api_host:
        gid = str(GREEN_API_ID).strip()
        if len(gid) >= 4 and gid[:4].isdigit():
            api_host = f"https://{gid[:4]}.api.green-api.com"
        else:
            api_host = "https://api.green-api.com"

    url = f"{api_host}/waInstance{GREEN_API_ID}/sendMessage/{GREEN_API_TOKEN}"
    try:
        payload = {"chatId": chat_id, "message": text}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=12) as resp:
                resp_txt = await resp.text()
                print(f"WhatsApp reply to {chat_id} | Status: {resp.status} | Host: {api_host} | Resp: {resp_txt[:80]}")
    except Exception as e:
        print(f"Error sending WhatsApp reply: {e}")

async def whatsapp_webhook(request):
    try:
        # 1. GREEN-API INCOMING WEBHOOK (JSON FORMAT - QR SCAN METHOD)
        if request.content_type == "application/json" or "application/json" in request.headers.get("Content-Type", ""):
            data = await request.json()
            type_webhook = data.get("typeWebhook")
            if type_webhook != "incomingMessageReceived":
                return web.Response(text="OK")

            sender_data = data.get("senderData", {})
            chat_id = sender_data.get("chatId", "")
            sender_name = sender_data.get("senderName", "Admin")
            
            message_data = data.get("messageData", {})
            type_msg = message_data.get("typeMessage")
            
            body = ""
            media_url = None
            if type_msg == "textMessage":
                body = message_data.get("textMessageData", {}).get("textMessage", "").strip()
            elif type_msg in ["imageMessage", "documentMessage"]:
                body = message_data.get("imageMessageData", {}).get("caption", "Nova yeh photo dekho aur batao!")
                media_url = message_data.get("imageMessageData", {}).get("downloadUrl")
            elif type_msg == "extendedTextMessage":
                body = message_data.get("extendedTextMessageData", {}).get("text", "").strip()
            else:
                return web.Response(text="OK")

            if not body and not media_url:
                return web.Response(text="OK")

            print(f" WhatsApp Msg from {sender_name} ({chat_id}): {body}")
            is_owner = True # Personal WhatsApp line is Admin's companion chat
            
            raw_reply = get_nova_response(sender_name, is_owner=is_owner, is_private=True, user_message=body, image_url=media_url)
            final_reply = fix_female_grammar(raw_reply)
            clean_reply = re.sub(r'\[ACTION:.*?\]', '', final_reply).strip()
            if not clean_reply:
                clean_reply = "Aapka hukum sar ankhon par mere Admin! "

            # Archive conversation for Global Long-Term Memory
            bot_data["conversation_archive"].append({
                "user": f"WhatsApp ({sender_name})",
                "msg": body[:150],
                "reply": clean_reply[:150],
                "time": str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            })
            save_data(bot_data)

            # Send reply back via Green-API
            await send_whatsapp_green_api(chat_id, clean_reply)
            return web.Response(text="OK")

        # 2. TWILIO INCOMING WEBHOOK (FORM-DATA FORMAT FALLBACK)
        else:
            data = await request.post()
            from_num = data.get("From", "")
            profile_name = data.get("ProfileName", "Admin")
            body = data.get("Body", "").strip()
            num_media = int(data.get("NumMedia", 0)) if data.get("NumMedia") else 0
            media_url = data.get("MediaUrl0") if num_media > 0 else None

            print(f" WhatsApp Msg from {profile_name} ({from_num}): {body}")
            is_owner = True
            sender_name = "Admin"

            if media_url and not body:
                body = "Nova yeh photo dekho aur batao kaisi hai!"
            elif not body:
                body = "Hello Nova!"

            raw_reply = get_nova_response(sender_name, is_owner=is_owner, is_private=True, user_message=body, image_url=media_url)
            final_reply = fix_female_grammar(raw_reply)
            clean_reply = re.sub(r'\[ACTION:.*?\]', '', final_reply).strip()
            if not clean_reply:
                clean_reply = "Aapka hukum sar ankhon par mere Admin! "

            bot_data["conversation_archive"].append({
                "user": f"WhatsApp ({profile_name})",
                "msg": body[:150],
                "reply": clean_reply[:150],
                "time": str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            })
            save_data(bot_data)

            safe_xml = html.escape(clean_reply)
            twiml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n    <Message>{safe_xml}</Message>\n</Response>'
            return web.Response(text=twiml, content_type="text/xml")
    except Exception as e:
        print(f"WhatsApp webhook error: {e}")
        return web.Response(text="OK")

# ====================  STARTUP & RUNNER ====================
async def main():
    # In unified deployment, WhatsApp (index.js) binds to process.env.PORT for Render health checks.
    # To prevent port collisions (EADDRINUSE), Discord bot only opens a web port if explicitly enabled.
    enable_web = os.environ.get("ENABLE_DISCORD_WEB", "0").lower() in ("1", "true", "yes")
    if enable_web:
        try:
            app = web.Application()
            app.router.add_get('/', lambda r: web.Response(text=" Nova AI Discord Bot is Online!"))
            runner = web.AppRunner(app)
            await runner.setup()
            port = int(os.environ.get("DISCORD_PORT", 10001))
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            print(f" Discord Web Server started on port {port}")
        except Exception as e:
            print(f"Web server start notice: {e}")

    if not DISCORD_BOT_TOKEN:
        print(" [DISCORD ERROR] DISCORD_BOT_TOKEN environment variable is missing! Please add it in Render Environment Variables.")
        while True:
            await asyncio.sleep(60)

    print(" [DISCORD] Logging into Discord Gateway...")
    async with bot:
        await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
