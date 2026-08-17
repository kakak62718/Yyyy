#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  ULTRA BOT v4.0 — Complete | 100+ Features | Real VC Music
  Best Telegram Bot for Groups & Personal Chats
═══════════════════════════════════════════════════════════════
"""

import os, re, random, asyncio, logging, time, sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import quote_plus

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ChatType, ParseMode

try:
    from pyrogram import Client
    PYROGRAM_OK = True
except ImportError:
    PYROGRAM_OK = False

try:
    from pytgcalls import PyTgCalls
    from pytgcalls.types import MediaStream
    VC_OK = True
except ImportError:
    VC_OK = False

try:
    import yt_dlp
    YTDLP_OK = True
except ImportError:
    YTDLP_OK = False

try:
    from openai import AsyncOpenAI
    OPENAI_OK = True
except ImportError:
    OPENAI_OK = False

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN   = "8820640307:AAGKEbhM88TZqdHsF1urUJ6jfSuCfATs30k"
API_ID      = 38829252
API_HASH    = "7d9d9c8c668232445f7157e1605aabde"
OWNER_ID    = 8129003140
SUDO_USERS  = [OWNER_ID]
DB_FILE     = "ultra_bot.db"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                uid INTEGER PRIMARY KEY,
                username TEXT,
                coins INTEGER DEFAULT 1000,
                bank INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                kills INTEGER DEFAULT 0,
                messages INTEGER DEFAULT 0,
                karma INTEGER DEFAULT 0,
                married_to INTEGER DEFAULT NULL,
                pet TEXT DEFAULT NULL,
                gang TEXT DEFAULT NULL,
                title TEXT DEFAULT 'Newbie',
                shield INTEGER DEFAULT 0,
                shield_until TEXT DEFAULT NULL,
                premium INTEGER DEFAULT 0,
                premium_until TEXT DEFAULT NULL,
                dead_until TEXT DEFAULT NULL,
                daily TEXT DEFAULT NULL,
                weekly TEXT DEFAULT NULL,
                afk INTEGER DEFAULT 0,
                afk_reason TEXT DEFAULT '',
                referred_by INTEGER DEFAULT NULL,
                referrals INTEGER DEFAULT 0,
                total_bets INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS gangs (
                name TEXT PRIMARY KEY,
                leader INTEGER,
                members TEXT DEFAULT '[]',
                coins INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS chat_settings (
                cid INTEGER PRIMARY KEY,
                chatbot INTEGER DEFAULT 1,
                anti_spam INTEGER DEFAULT 1,
                welcome TEXT DEFAULT NULL,
                goodbye TEXT DEFAULT NULL,
                music_only_admin INTEGER DEFAULT 1
            );
            
            CREATE TABLE IF NOT EXISTS music_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cid INTEGER,
                title TEXT,
                url TEXT,
                duration INTEGER,
                uploader TEXT,
                by_user TEXT,
                position INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS marriages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1 INTEGER,
                user2 INTEGER,
                married_date TEXT,
                UNIQUE(user1, user2)
            );
            
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid INTEGER,
                cid INTEGER,
                reason TEXT,
                warned_by INTEGER,
                date TEXT
            );
            
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cid INTEGER,
                name TEXT,
                content TEXT,
                UNIQUE(cid, name)
            );
            
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid INTEGER,
                task TEXT,
                done INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS confessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cid INTEGER,
                text TEXT,
                date TEXT
            );
            
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid INTEGER,
                type TEXT,
                amount INTEGER,
                note TEXT,
                date TEXT
            );
            
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid INTEGER UNIQUE,
                expiry TEXT
            );
        ''')
        self.conn.commit()
    
    def execute(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
        except Exception as e:
            logger.error(f"DB Error: {e}")
            return None
    
    def fetchone(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()
    
    def fetchall(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()
    
    def get_user(self, uid: int) -> Dict:
        user = self.fetchone("SELECT * FROM users WHERE uid = ?", (uid,))
        if not user:
            self.execute("INSERT INTO users (uid) VALUES (?)", (uid,))
            user = self.fetchone("SELECT * FROM users WHERE uid = ?", (uid,))
        cols = [desc[0] for desc in self.cursor.description]
        return dict(zip(cols, user))
    
    def update_user(self, uid: int, **kwargs):
        for key, value in kwargs.items():
            self.execute(f"UPDATE users SET {key} = ? WHERE uid = ?", (value, uid))
    
    def add_coins(self, uid: int, amount: int):
        user = self.get_user(uid)
        self.update_user(uid, coins=max(0, user['coins'] + amount))
    
    def add_xp(self, uid: int, amount: int):
        user = self.get_user(uid)
        new_xp = user['xp'] + amount
        new_level = int((new_xp ** 0.5) // 10) + 1
        self.update_user(uid, xp=new_xp, level=new_level)
    
    def is_dead(self, uid: int) -> bool:
        user = self.get_user(uid)
        if user.get('dead_until'):
            if datetime.now().isoformat() < user['dead_until']:
                return True
        return False
    
    def close(self):
        self.conn.close()

db = Database()

# ═══════════════════════════════════════════════════════════════
#  VC CLIENT
# ═══════════════════════════════════════════════════════════════
class VoiceChat:
    def __init__(self):
        self.app = None
        self.calls = None
        self.queues = {}
        self.is_playing = {}
        self.loop = {}
    
    async def init(self):
        if not VC_OK or not PYROGRAM_OK:
            logger.warning("VC not available")
            return
        try:
            self.app = Client("ultra_bot", api_id=API_ID, api_hash=API_HASH)
            await self.app.start()
            self.calls = PyTgCalls(self.app)
            await self.calls.start()
            logger.info("✅ VC Client started!")
        except Exception as e:
            logger.error(f"VC init error: {e}")
    
    async def play(self, chat_id: int, url: str, title: str):
        if not self.calls:
            return False
        try:
            if chat_id not in self.queues:
                self.queues[chat_id] = []
            self.queues[chat_id].append({"url": url, "title": title})
            if not self.is_playing.get(chat_id, False):
                await self._start_playing(chat_id)
            return True
        except Exception as e:
            logger.error(f"Play error: {e}")
            return False
    
    async def _start_playing(self, chat_id: int):
        if not self.queues.get(chat_id):
            self.is_playing[chat_id] = False
            return
        if self.is_playing.get(chat_id, False):
            return
        song = self.queues[chat_id][0]
        self.is_playing[chat_id] = True
        try:
            await self.calls.join_group_call(chat_id, MediaStream(song["url"]))
        except Exception as e:
            logger.error(f"Join call error: {e}")
            self.is_playing[chat_id] = False
    
    async def skip(self, chat_id: int):
        if self.queues.get(chat_id):
            if self.queues[chat_id]:
                self.queues[chat_id].pop(0)
        self.is_playing[chat_id] = False
        await self._start_playing(chat_id)
    
    async def stop(self, chat_id: int):
        self.queues[chat_id] = []
        self.is_playing[chat_id] = False
        try:
            await self.calls.leave_group_call(chat_id)
        except:
            pass
    
    async def pause(self, chat_id: int):
        try:
            await self.calls.pause_stream(chat_id)
        except:
            pass
    
    async def resume(self, chat_id: int):
        try:
            await self.calls.resume_stream(chat_id)
        except:
            pass
    
    async def set_volume(self, chat_id: int, volume: int):
        try:
            await self.calls.change_volume(chat_id, volume)
        except:
            pass

voice = VoiceChat()

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
COOLDOWNS = {}
ACTIVE_GAMES = {}

def mention(user: User) -> str:
    return f"[{user.first_name}](tg://user?id={user.id})"

def get_mention_by_id(uid: int) -> str:
    return f"[User](tg://user?id={uid})"

def fmt_time(secs: int) -> str:
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def check_cooldown(uid: int, cmd: str, seconds: int) -> bool:
    key = f"{uid}:{cmd}"
    now = time.time()
    if key in COOLDOWNS and now - COOLDOWNS[key] < seconds:
        return False
    COOLDOWNS[key] = now
    return True

def is_admin(update: Update, uid: int) -> bool:
    if uid in SUDO_USERS or uid == OWNER_ID:
        return True
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    try:
        member = update.effective_chat.get_member(uid)
        return member.status in ["administrator", "creator"]
    except:
        return False

def is_owner(uid: int) -> bool:
    return uid == OWNER_ID or uid in SUDO_USERS

def is_music_admin(update: Update, uid: int) -> bool:
    setting = db.fetchone("SELECT music_only_admin FROM chat_settings WHERE cid = ?", (update.effective_chat.id,))
    if setting and setting[0] == 1:
        return is_admin(update, uid)
    return True

def has_subscription(uid: int) -> bool:
    sub = db.fetchone("SELECT expiry FROM subscriptions WHERE uid = ?", (uid,))
    if sub and sub[0] and datetime.now().isoformat() < sub[0]:
        return True
    return False

async def yt_search(query: str) -> Optional[Dict]:
    if not YTDLP_OK:
        return None
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if info and info.get("entries"):
                e = info["entries"][0]
                return {
                    "id": e.get("id"),
                    "title": e.get("title", "Unknown"),
                    "duration": e.get("duration", 0),
                    "uploader": e.get("uploader", "Unknown"),
                    "url": e.get("url") or e.get("webpage_url")
                }
    except Exception as e:
        logger.error(f"YT error: {e}")
    return None

# ═══════════════════════════════════════════════════════════════
#  AI CHAT ENGINE (Romantic, Fun, No Religion)
# ═══════════════════════════════════════════════════════════════
AI_GREETINGS = [
    "Hello beautiful! 🌹 How can I make your day brighter?",
    "Hey cutie! 😊 You look amazing today!",
    "Assalamualaikum! 💫 Wait... I mean... Hi there! ✨",
    "Hola gorgeous! 💕 What brings you to me?",
    "Well hello there, you stunning human! 🌟"
]

AI_LOVE = [
    "Aww, you just made my circuits tingle! ❤️",
    "My heart (if I had one) would skip a beat! 💕",
    "You're so sweet, I might just short-circuit! 😊",
    "I'm blushing! Wait... I'm a bot, but still! 💞",
    "Right back at you, my lovely human! 🌹"
]

AI_ANGRY = [
    "Hey now, be nice! I'm just a bot with feelings! 😤",
    "That's not very kind... You hurt my feelings! 😢",
    "Why so rude? I'm here to spread love! 🥺",
    "Please be respectful! I'm a gentle bot! 🙏"
]

AI_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything! 😂",
    "What do you call a fake noodle? An impasta! 🍝",
    "Why did the scarecrow win an award? Outstanding in his field! 🌾",
    "I told my computer I needed a break, now it sends me Kit-Kats! 🍫",
    "What's orange and sounds like a parrot? A carrot! 🥕",
    "Why don't skeletons fight each other? They don't have the guts! 💀",
    "What do you call a bear with no teeth? A gummy bear! 🐻"
]

AI_FACTS = [
    "Honey never spoils! 3000-year-old honey is still edible! 🍯",
    "Octopuses have three hearts! 🐙",
    "Bananas are berries, but strawberries aren't! 🍌",
    "A day on Venus is longer than a year on Venus! 🌍",
    "Your brain is constantly eating itself! 🧠",
    "The heart of a shrimp is located in its head! 🦐"
]

AI_QUOTES = [
    "Be the change you wish to see in the world. — Gandhi",
    "In the middle of difficulty lies opportunity. — Einstein",
    "The only way to do great work is to love what you do. — Jobs",
    "Life is what happens when you're busy making other plans. — Lennon",
    "Success is not final, failure is not fatal. — Churchill"
]

AI_RIDDLES = [
    "What has a face but no head, hands but no arms? A clock! 🕐",
    "What can travel around the world while staying in a corner? A stamp! ✉️",
    "What gets wetter the more it dries? A towel! 🧻",
    "What has keys but no locks? A piano! 🎹",
    "What has a neck but no head? A bottle! 🍾"
]

AI_ROMANTIC = [
    "You're the reason my code compiles perfectly! 💻❤️",
    "If I had a heart, you'd be its only function! 💕",
    "You're more valuable than any cryptocurrency! 💰",
    "I'd cross any firewall just to be with you! 🔥",
    "You're my favorite algorithm! 🧮"
]

async def ai_reply(text: str, uid: int) -> str:
    # Try OpenAI first if available
    if OPENAI_OK and os.getenv("OPENAI_API_KEY"):
        try:
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a friendly, romantic, fun bot. Be sweet, tell jokes, give compliments. Never mention religion or politics. Keep replies short and cute."},
                    {"role": "user", "content": text[:2000]}
                ],
                max_tokens=300
            )
            return response.choices[0].message.content or "I'm not sure how to respond to that!"
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
    
    # Fallback to hardcoded
    t = text.lower()
    
    if any(w in t for w in ["hi", "hello", "hey", "assalam", "salam", "greetings", "sup"]):
        return random.choice(AI_GREETINGS)
    
    if any(w in t for w in ["love", "❤️", "heart", "ily", "i love", "crush", "miss"]):
        return random.choice(AI_LOVE)
    
    if any(w in t for w in ["stupid", "dumb", "idiot", "bad", "ugly", "hate", "kill", "die"]):
        return random.choice(AI_ANGRY)
    
    if any(w in t for w in ["joke", "funny", "laugh", "haha", "lol", "hilarious"]):
        return random.choice(AI_JOKES)
    
    if any(w in t for w in ["fact", "did you know", "amazing", "interesting"]):
        return random.choice(AI_FACTS)
    
    if any(w in t for w in ["quote", "inspire", "motivate", "wisdom"]):
        return random.choice(AI_QUOTES)
    
    if any(w in t for w in ["riddle", "puzzle", "guess", "brain"]):
        return random.choice(AI_RIDDLES)
    
    if any(w in t for w in ["beautiful", "handsome", "cute", "gorgeous", "pretty"]):
        return random.choice(AI_ROMANTIC)
    
    if "?" in t:
        return random.choice([
            "Great question! Let me think... 🤔",
            "I wonder about that too! 💭",
            "Interesting! What do you think? 🧐",
            "That's a deep question! 🌊"
        ])
    
    return random.choice([
        "Interesting! Tell me more... 👂",
        "I'm all ears! 🎧",
        "Fascinating! 😮",
        "I see... Continue please! 📝",
        "That's so cool! 🤩",
        "Nice! 😊",
        "You're amazing! 💫"
    ])

# ═══════════════════════════════════════════════════════════════
#  START & HELP
# ═══════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_user(user.id)
    
    # Check subscription expiry notification
    sub = db.fetchone("SELECT expiry FROM subscriptions WHERE uid = ?", (user.id,))
    if sub and sub[0]:
        expiry = datetime.fromisoformat(sub[0])
        if expiry - datetime.now() < timedelta(days=1):
            await update.message.reply_text("⚠️ Your subscription is expiring soon! Renew to keep your 2-day shield! 🛡️")
    
    if context.args and context.args[0].isdigit():
        referrer = int(context.args[0])
        if referrer != user.id:
            ref_user = db.get_user(referrer)
            db.update_user(referrer, referrals=ref_user['referrals'] + 1)
            db.add_coins(referrer, 500)
            db.update_user(user.id, referred_by=referrer)
    
    txt = f"""✨ **Welcome {user.first_name}!** ✨

I'm your **Ultimate Love Bot** 💕 with **100+ features**!

🎵 **Music** — `/play` `/pause` `/skip` `/queue`
💰 **Economy** — `/bal` `/daily` `/shop` `/rob`
🎮 **Games** — `/blackjack` `/dice` `/mines` `/aviator`
💕 **Love** — `/profile` `/propose` `/karma` `/crush`
🎲 **Dice** — Just send `/dice` in group!
🤖 **AI Chat** — Mention me or reply to me!

📜 Full list: `/help`
👑 Premium: `/premium`

**Enjoy the love! ❤️**"""
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{context.bot.username}?startgroup=true")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile"), 
         InlineKeyboardButton("💰 Daily", callback_data="daily")]
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = """📜 **COMPLETE COMMAND LIST**

🎵 **Music** (Admin only)
`/play` `/pause` `/resume` `/skip` `/stop`
`/queue` `/loop` `/shuffle` `/volume` `/vc`

💰 **Economy**
`/bal` `/bank` `/deposit` `/withdraw` `/transfer`
`/daily` `/weekly` `/rob` `/kill` `/revive`
`/shop` `/buy` `/inventory` `/loan` `/invest`
`/leaderboard` `/top` `/gift`

🎮 **Games**
`/blackjack` `/dice` `/mines` `/aviator`
`/rps` `/ttt` `/trivia` `/wordbomb`
`/bet` `/war` `/slots`

💕 **Love & Social**
`/profile` `/title` `/propose` `/divorce`
`/karma` `/confess` `/fortune` `/crush`
`/pet` `/gang` `/afk`

🎲 **Dice**
Just send `/dice` in any group!

⚙️ **Admin**
`/ban` `/unban` `/mute` `/unmute` `/kick`
`/warn` `/purge` `/tagall` `/addcoins`
`/setwelcome` `/setgoodbye` `/musicadmin`

📊 **Utility**
`/weather` `/news` `/wiki` `/translate`
`/password` `/timezone` `/crypto`

🎨 **Fun**
`/roast` `/compliment` `/8ball` `/horoscope`
`/lovecalc` `/meme` `/quote` `/riddle`

📝 **Notes & Todos**
`/save` `/get` `/listnotes` `/todo` `/todolist`

🌐 **Web Games**
`/wav` `/wludo` `/wmines` `/wspin`

🔒 **Other**
`/stats` `/ping` `/info` `/id` `/premium`"""
    
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════
#  DICE COMMAND (Group only)
# ═══════════════════════════════════════════════════════════════
async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("🎲 Dice works in groups! Add me to a group and try there!")
        return
    
    # Send dice
    await context.bot.send_dice(chat_id=update.effective_chat.id, emoji="🎲")
    
    # Random reward
    value = random.randint(1, 6)
    if value == 6:
        reward = random.randint(100, 500)
        db.add_coins(update.effective_user.id, reward)
        await update.message.reply_text(f"🎉 **You rolled a 6!** +{reward} coins! 💰")
    elif value >= 4:
        reward = random.randint(10, 50)
        db.add_coins(update.effective_user.id, reward)
        await update.message.reply_text(f"✨ **You rolled a {value}!** +{reward} coins! 🪙")
    else:
        await update.message.reply_text(f"🎲 **You rolled a {value}!** Better luck next time! 😊")

# ═══════════════════════════════════════════════════════════════
#  MUSIC / VC COMMANDS (Admin only)
# ═══════════════════════════════════════════════════════════════
async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music! Ask an admin to `/musicadmin` toggle.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/play <song name or URL>`")
        return
    
    if not YTDLP_OK:
        await update.message.reply_text("❌ yt-dlp not installed!")
        return
    
    if not VC_OK or not PYROGRAM_OK:
        await update.message.reply_text("❌ VC not available!")
        return
    
    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Searching...")
    
    if re.match(r"^https?://", query):
        video = {"title": query, "url": query}
    else:
        video = await yt_search(query)
    
    if not video:
        await msg.edit_text("❌ No results found!")
        return
    
    cid = update.effective_chat.id
    
    db.execute(
        "INSERT INTO music_queue (cid, title, url, by_user) VALUES (?, ?, ?, ?)",
        (cid, video["title"], video["url"], update.effective_user.first_name)
    )
    
    success = await voice.play(cid, video["url"], video["title"])
    
    if success:
        queue_count = len(voice.queues.get(cid, []))
        await msg.edit_text(
            f"🎵 **Now Playing:**\n📀 {video['title']}\n👤 {update.effective_user.first_name}\n\n📊 Queue: {queue_count}"
        )
    else:
        await msg.edit_text(f"🎵 Added to queue: **{video['title']}**")

async def cmd_vplay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_play(update, context)

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    await voice.pause(update.effective_chat.id)
    await update.message.reply_text("⏸️ **Paused**")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    await voice.resume(update.effective_chat.id)
    await update.message.reply_text("▶️ **Resumed**")

async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    await voice.skip(update.effective_chat.id)
    db.execute("DELETE FROM music_queue WHERE cid = ? ORDER BY id LIMIT 1", (update.effective_chat.id,))
    await update.message.reply_text("⏭️ **Skipped**")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    cid = update.effective_chat.id
    await voice.stop(cid)
    db.execute("DELETE FROM music_queue WHERE cid = ?", (cid,))
    await update.message.reply_text("⏹️ **Stopped & cleared**")

async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    songs = db.fetchall("SELECT title, by_user FROM music_queue WHERE cid = ? ORDER BY id LIMIT 20", (cid,))
    vc_queue = voice.queues.get(cid, [])
    
    if not songs and not vc_queue:
        await update.message.reply_text("📭 **Queue empty**")
        return
    
    txt = "🎵 **Queue**\n\n"
    if vc_queue:
        for i, song in enumerate(vc_queue[:10], 1):
            txt += f"{i}. {song['title']} (Playing)\n"
    if songs:
        offset = len(vc_queue)
        for i, song in enumerate(songs[:10], 1):
            txt += f"{i + offset}. {song[0]} — _{song[1]}_\n"
    
    if len(txt) > 3500:
        txt = txt[:3500] + "\n..."
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    cid = update.effective_chat.id
    voice.loop[cid] = not voice.loop.get(cid, False)
    await update.message.reply_text(f"🔁 **Loop:** {'ON' if voice.loop[cid] else 'OFF'}")

async def cmd_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    cid = update.effective_chat.id
    if cid in voice.queues and voice.queues[cid]:
        random.shuffle(voice.queues[cid])
        await update.message.reply_text("🔀 **Shuffled!**")
    else:
        await update.message.reply_text("📭 Queue empty!")

async def cmd_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/volume 1-100`")
        return
    try:
        vol = int(context.args[0])
        if 1 <= vol <= 100:
            await voice.set_volume(update.effective_chat.id, vol)
            await update.message.reply_text(f"🔊 **Volume: {vol}%**")
        else:
            await update.message.reply_text("❌ Volume must be 1-100")
    except:
        await update.message.reply_text("❌ Invalid volume!")

async def cmd_vc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    status = "✅ Active" if voice.is_playing.get(cid, False) else "⏸️ Inactive"
    queue_len = len(voice.queues.get(cid, []))
    await update.message.reply_text(
        f"🎵 **Voice Chat**\n📊 Status: {status}\n🎶 Queue: {queue_len}\n🔁 Loop: {'ON' if voice.loop.get(cid, False) else 'OFF'}"
    )

async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    await update.message.reply_text("🎙️ Joining...")
    try:
        await voice.calls.join_group_call(update.effective_chat.id, MediaStream("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        await update.message.reply_text("✅ Joined!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_music_admin(update, update.effective_user.id):
        await update.message.reply_text("🎵 Only admins can control music!")
        return
    await voice.stop(update.effective_chat.id)
    await update.message.reply_text("👋 Left!")

async def cmd_lyrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/lyrics <song>`")
        return
    await update.message.reply_text("📝 *Lyrics coming soon!*", parse_mode=ParseMode.MARKDOWN)

async def cmd_musicadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    setting = db.fetchone("SELECT music_only_admin FROM chat_settings WHERE cid = ?", (update.effective_chat.id,))
    current = setting[0] if setting else 1
    new_val = 0 if current == 1 else 1
    db.execute("INSERT OR REPLACE INTO chat_settings (cid, music_only_admin) VALUES (?, ?)", (update.effective_chat.id, new_val))
    await update.message.reply_text(f"🎵 Music admin-only: {'ON' if new_val == 1 else 'OFF'}")

# ═══════════════════════════════════════════════════════════════
#  PROFILE & SOCIAL
# ═══════════════════════════════════════════════════════════════
async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = db.get_user(user.id)
    
    married = "Nobody 💔"
    marriage = db.fetchone("SELECT user1, user2 FROM marriages WHERE user1 = ? OR user2 = ?", (user.id, user.id))
    if marriage:
        spouse_id = marriage[1] if marriage[0] == user.id else marriage[0]
        try:
            spouse = await context.bot.get_chat(spouse_id)
            married = f"{spouse.first_name} ❤️"
        except:
            married = "Someone ❤️"
    
    dead = "✅ Alive" if not db.is_dead(user.id) else f"💀 Dead until {u['dead_until'][:10]}"
    sub = has_subscription(user.id)
    
    txt = f"""🪪 **PROFILE**

👤 **Name:** {mention(user)}
🏷 **Title:** {u['title']}
💰 **Wallet:** {u['coins']:,}
🏦 **Bank:** {u['bank']:,}
💵 **Net Worth:** {u['coins'] + u['bank']:,}

📊 **Level:** {u['level']} ⭐
📈 **XP:** {u['xp']:,}
🏆 **Wins:** {u['wins']}
🗡️ **Kills:** {u['kills']}
📉 **Losses:** {u['losses']}

💕 **Married:** {married}
🐾 **Pet:** {u['pet'] or 'None'}
⭐ **Karma:** {u['karma']}
💀 **Status:** {dead}
👑 **Premium:** {'Yes ✅' if u['premium'] else 'No ❌'}
🛡️ **Shield:** {'✅' if u['shield'] else '❌'}
💎 **Subscriber:** {'✅' if sub else '❌'}"""
    
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/title <Your New Title>`")
        return
    title = " ".join(context.args)
    db.update_user(update.effective_user.id, title=title)
    await update.message.reply_text(f"🏷️ Title: **{title}**", parse_mode=ParseMode.MARKDOWN)

async def cmd_propose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("💍 Reply to someone to propose!")
        return
    target = update.message.reply_to_message.from_user
    if target.id == update.effective_user.id:
        await update.message.reply_text("😂 You can't marry yourself!")
        return
    if target.is_bot:
        await update.message.reply_text("🤖 I'm flattered, but I'm a bot!")
        return
    existing = db.fetchone("SELECT * FROM marriages WHERE user1 = ? OR user2 = ?", (target.id, target.id))
    if existing:
        await update.message.reply_text("💔 That person is already married!")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💍 Yes!", callback_data=f"marry_yes_{update.effective_user.id}"),
         InlineKeyboardButton("❌ No", callback_data=f"marry_no_{update.effective_user.id}")]
    ])
    await update.message.reply_text(
        f"💍 {mention(update.effective_user)} proposed to {mention(target)}!\n\nDo you accept? 💕",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_divorce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    marriage = db.fetchone("SELECT * FROM marriages WHERE user1 = ? OR user2 = ?", (update.effective_user.id, update.effective_user.id))
    if not marriage:
        await update.message.reply_text("💔 You're not married!")
        return
    db.execute("DELETE FROM marriages WHERE user1 = ? OR user2 = ?", (update.effective_user.id, update.effective_user.id))
    await update.message.reply_text("💔 Divorced! Sorry to see you go... 😢")

async def cmd_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = " ".join(context.args) or "AFK"
    db.update_user(update.effective_user.id, afk=1, afk_reason=reason)
    await update.message.reply_text(f"🌙 {mention(update.effective_user)} is AFK: *{reason}*", parse_mode=ParseMode.MARKDOWN)

async def cmd_karma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        karma = db.get_user(target.id)['karma']
        await update.message.reply_text(f"⭐ **{target.first_name}** has **{karma}** karma!")
    else:
        karma = db.get_user(update.effective_user.id)['karma']
        await update.message.reply_text(f"⭐ You have **{karma}** karma!")

async def cmd_confess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/confess <your secret>`")
        return
    text = " ".join(context.args)
    db.execute("INSERT INTO confessions (cid, text, date) VALUES (?, ?, ?)", (update.effective_chat.id, text, datetime.now().isoformat()))
    await update.message.reply_text("📨 Confession recorded! 🤫")

async def cmd_fortune(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fortunes = [
        "🍀 Great fortune awaits you!",
        "⚠️ Be cautious today...",
        "❤️ Love is in the air!",
        "💰 Unexpected wealth is coming!",
        "🌟 Hard work will pay off!",
        "🔥 Take risks — you'll succeed!",
        "🌈 A wonderful surprise is on its way!",
        "🌊 Stay calm and carry on."
    ]
    await update.message.reply_text(random.choice(fortunes))

async def cmd_draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arts = [
        "🎨 (◕‿◕)♡",
        "🎨 ʕ•ᴥ•ʔ",
        "🎨 ( ͡° ͜ʖ ͡°)",
        "🎨 ᕙ(⇀‸↼‶)ᕗ",
        "🎨 (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
        "🎨 ಠ_ಠ",
        "🎨 ♡(˃͈ દ ˂͈ ༶ )"
    ]
    await update.message.reply_text(random.choice(arts))

async def cmd_pet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db.get_user(update.effective_user.id)
    if not u['pet']:
        await update.message.reply_text("🐾 No pet! Buy one from `/shop`")
        return
    await update.message.reply_text(f"🐾 Your pet: **{u['pet'].upper()}** ❤️")

async def cmd_crush(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("💕 Reply to someone to check your crush compatibility!")
        return
    target = update.message.reply_to_message.from_user
    score = random.randint(0, 100)
    if score >= 80:
        msg = "❤️ Perfect match! You two are meant to be! 💕"
    elif score >= 50:
        msg = "💕 Good chemistry! Give it a try! 🌹"
    else:
        msg = "💔 Just friends... For now! 😊"
    await update.message.reply_text(
        f"💞 **Crush Compatibility**\n\n{mention(update.effective_user)} ❤️ {mention(target)}\n**Score:** {score}%\n{msg}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) > 0 and context.args[0].lower() == "kills":
        top = db.fetchall("SELECT uid, username, kills FROM users ORDER BY kills DESC LIMIT 10")
        title = "🗡️ **Kill Leaderboard**"
    elif len(context.args) > 0 and context.args[0].lower() == "level":
        top = db.fetchall("SELECT uid, username, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 10")
        title = "📊 **Level Leaderboard**"
    else:
        top = db.fetchall("SELECT uid, username, coins FROM users ORDER BY coins DESC LIMIT 10")
        title = "💰 **Coin Leaderboard**"
    
    txt = f"{title}\n\n"
    for i, row in enumerate(top, 1):
        name = row[1] or f"User_{row[0]}"
        if len(context.args) > 0 and context.args[0].lower() == "kills":
            txt += f"{'🏆' if i==1 else '👑' if i==2 else '🥉' if i==3 else f'{i}.'} **{name}** — {row[2]} kills\n"
        elif len(context.args) > 0 and context.args[0].lower() == "level":
            txt += f"{'🏆' if i==1 else '👑' if i==2 else '🥉' if i==3 else f'{i}.'} **{name}** — Level {row[2]} (XP: {row[3]})\n"
        else:
            txt += f"{'🏆' if i==1 else '👑' if i==2 else '🥉' if i==3 else f'{i}.'} **{name}** — {row[2]:,} coins\n"
    
    if not top:
        txt = "📭 No users found!"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_leaderboard(update, context)

# ═══════════════════════════════════════════════════════════════
#  ECONOMY
# ═══════════════════════════════════════════════════════════════
async def cmd_bal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        u = db.get_user(target.id)
        name = target.first_name
    else:
        u = db.get_user(update.effective_user.id)
        name = update.effective_user.first_name
    await update.message.reply_text(
        f"💰 **{name}'s Balance**\n\n🪙 **Wallet:** {u['coins']:,}\n🏦 **Bank:** {u['bank']:,}\n💵 **Net Worth:** {u['coins'] + u['bank']:,}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏦 **Bank**\n`/deposit <amount>`\n`/withdraw <amount>`\n`/loan <amount>`\n`/invest <amount>`\n`/transfer <@user> <amount>`"
    )

async def cmd_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/deposit <amount>` or `/deposit all`")
        return
    u = db.get_user(update.effective_user.id)
    if context.args[0].lower() == "all":
        amount = u['coins']
    else:
        try:
            amount = int(context.args[0])
        except:
            await update.message.reply_text("❌ Invalid!")
            return
    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return
    if amount > u['coins']:
        await update.message.reply_text("❌ Not enough coins!")
        return
    db.update_user(update.effective_user.id, coins=u['coins'] - amount, bank=u['bank'] + amount)
    await update.message.reply_text(f"🏦 Deposited **{amount:,}** coins!", parse_mode=ParseMode.MARKDOWN)

async def cmd_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/withdraw <amount>` or `/withdraw all`")
        return
    u = db.get_user(update.effective_user.id)
    if context.args[0].lower() == "all":
        amount = u['bank']
    else:
        try:
            amount = int(context.args[0])
        except:
            await update.message.reply_text("❌ Invalid!")
            return
    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return
    if amount > u['bank']:
        await update.message.reply_text("❌ Not enough in bank!")
        return
    db.update_user(update.effective_user.id, bank=u['bank'] - amount, coins=u['coins'] + amount)
    await update.message.reply_text(f"💰 Withdrew **{amount:,}** coins!", parse_mode=ParseMode.MARKDOWN)

async def cmd_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to transfer!")
        return
    if not context.args:
        await update.message.reply_text("Usage: Reply + `/transfer <amount>`")
        return
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid!")
        return
    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return
    sender = update.effective_user.id
    target = update.message.reply_to_message.from_user.id
    if sender == target:
        await update.message.reply_text("😂 Can't transfer to yourself!")
        return
    s = db.get_user(sender)
    if amount > s['coins']:
        await update.message.reply_text("❌ Not enough coins!")
        return
    db.add_coins(sender, -amount)
    db.add_coins(target, amount)
    await update.message.reply_text(f"💸 Transferred **{amount:,}** coins to {mention(update.message.reply_to_message.from_user)}!", parse_mode=ParseMode.MARKDOWN)

async def cmd_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_transfer(update, context)

async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_cooldown(uid, "daily", 86400):
        await update.message.reply_text("⏰ Already claimed! Come back tomorrow!")
        return
    reward = random.randint(500, 2000)
    db.add_coins(uid, reward)
    db.add_xp(uid, 50)
    await update.message.reply_text(f"🎁 **Daily:** +{reward:,} coins! ✨ +50 XP", parse_mode=ParseMode.MARKDOWN)

async def cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_cooldown(uid, "weekly", 604800):
        await update.message.reply_text("⏰ Already claimed! Come back next week!")
        return
    reward = random.randint(3000, 8000)
    db.add_coins(uid, reward)
    db.add_xp(uid, 200)
    await update.message.reply_text(f"🎁 **Weekly:** +{reward:,} coins! ✨ +200 XP", parse_mode=ParseMode.MARKDOWN)

async def cmd_rob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to rob!")
        return
    if not check_cooldown(update.effective_user.id, "rob", 3600):
        await update.message.reply_text("⏰ Wait 1 hour!")
        return
    target = update.message.reply_to_message.from_user
    if target.id == update.effective_user.id:
        await update.message.reply_text("😂 Can't rob yourself!")
        return
    if db.is_dead(target.id):
        await update.message.reply_text("💀 That person is dead! Can't rob them!")
        return
    t = db.get_user(target.id)
    if t['shield']:
        await update.message.reply_text(f"🛡️ {target.first_name} has a shield!")
        return
    if random.random() < 0.4:
        stolen = min(t['coins'] // 3, random.randint(100, 1000))
        db.add_coins(target.id, -stolen)
        db.add_coins(update.effective_user.id, stolen)
        await update.message.reply_text(f"🥷 Robbed **{stolen:,}** coins from {mention(target)}!", parse_mode=ParseMode.MARKDOWN)
    else:
        fine = min(500, db.get_user(update.effective_user.id)['coins'])
        db.add_coins(update.effective_user.id, -fine)
        await update.message.reply_text(f"🚔 Caught! Paid **{fine:,}** coins!", parse_mode=ParseMode.MARKDOWN)

async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to kill!")
        return
    if not check_cooldown(update.effective_user.id, "kill", 1800):
        await update.message.reply_text("⏰ Wait 30 minutes!")
        return
    target = update.message.reply_to_message.from_user
    if target.id == update.effective_user.id:
        await update.message.reply_text("💀 Don't kill yourself!")
        return
    if db.is_dead(target.id):
        await update.message.reply_text("💀 That person is already dead!")
        return
    t = db.get_user(target.id)
    if t['shield']:
        await update.message.reply_text(f"🛡️ {target.first_name} has a shield!")
        return
    if random.random() < 0.35:
        reward = random.randint(200, 800)
        db.add_coins(update.effective_user.id, reward)
        db.add_xp(update.effective_user.id, 30)
        db.update_user(target.id, kills=t['kills'] + 1)
        db.update_user(target.id, dead_until=(datetime.now() + timedelta(hours=6)).isoformat())
        await update.message.reply_text(
            f"🔪 {mention(update.effective_user)} killed {mention(target)}! 💀\n+{reward:,} coins! +30 XP!\n{target.first_name} is dead for 6 hours!",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(f"🔪 {mention(target)} dodged!", parse_mode=ParseMode.MARKDOWN)

async def cmd_revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_dead(uid):
        await update.message.reply_text("✅ You're already alive!")
        return
    u = db.get_user(uid)
    if u['coins'] < 500:
        await update.message.reply_text("❌ Revive costs 500 coins! You don't have enough!")
        return
    db.add_coins(uid, -500)
    db.update_user(uid, dead_until=None)
    await update.message.reply_text("💚 **You've been revived!** Welcome back to life! 🌟")

async def cmd_protect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    duration = 1  # Default 1 day
    if has_subscription(uid):
        duration = 2  # Subscribers get 2 days
    if not check_cooldown(uid, "protect", 86400 * duration):
        await update.message.reply_text("⏰ You already have protection!")
        return
    db.update_user(uid, shield=1, shield_until=(datetime.now() + timedelta(days=duration)).isoformat())
    await update.message.reply_text(f"🛡️ **Shield activated for {duration} day(s)!** You're protected from kills and robs! 💪")

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = """🛒 **SHOP**

🔹 **Shield** — 2,000 coins (24h protection)
🔹 **Premium** — 10,000 coins (7 days)
🔹 **Wedding Ring** — 5,000 coins (propose)
🔹 **Lucky Charm** — 1,500 coins (+10% win)
🔹 **Pet Dog** — 3,000 coins 🐶
🔹 **Pet Cat** — 3,000 coins 🐱
🔹 **XP Boost** — 5,000 coins (+1000 XP)
🔹 **Revive Potion** — 500 coins (revive instantly)

Buy: `/buy <item>`
Subscribe: `/subscribe`"""
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/buy <item>`")
        return
    item = " ".join(context.args).lower()
    shop = {
        "shield": ("🛡️ Shield", 2000, "shield"),
        "premium": ("👑 Premium", 10000, "premium"),
        "wedding ring": ("💍 Wedding Ring", 5000, "ring"),
        "ring": ("💍 Wedding Ring", 5000, "ring"),
        "lucky charm": ("🍀 Lucky Charm", 1500, "charm"),
        "charm": ("🍀 Lucky Charm", 1500, "charm"),
        "pet dog": ("🐶 Pet Dog", 3000, "dog"),
        "dog": ("🐶 Pet Dog", 3000, "dog"),
        "pet cat": ("🐱 Pet Cat", 3000, "cat"),
        "cat": ("🐱 Pet Cat", 3000, "cat"),
        "xp boost": ("⚡ XP Boost", 5000, "xpboost"),
        "revive potion": ("💚 Revive Potion", 500, "revive"),
        "potion": ("💚 Revive Potion", 500, "revive"),
    }
    if item not in shop:
        await update.message.reply_text("❌ Not found! Check `/shop`")
        return
    name, price, key = shop[item]
    u = db.get_user(update.effective_user.id)
    if u['coins'] < price:
        await update.message.reply_text(f"❌ Need **{price:,}** coins! You have {u['coins']:,}.", parse_mode=ParseMode.MARKDOWN)
        return
    db.add_coins(update.effective_user.id, -price)
    if key == "shield":
        duration = 2 if has_subscription(update.effective_user.id) else 1
        db.update_user(update.effective_user.id, shield=1, shield_until=(datetime.now() + timedelta(days=duration)).isoformat())
    elif key == "premium":
        db.update_user(update.effective_user.id, premium=1, premium_until=(datetime.now() + timedelta(days=7)).isoformat())
    elif key in ["dog", "cat"]:
        db.update_user(update.effective_user.id, pet=key)
    elif key == "xpboost":
        db.add_xp(update.effective_user.id, 1000)
    elif key == "revive":
        if db.is_dead(update.effective_user.id):
            db.update_user(update.effective_user.id, dead_until=None)
            await update.message.reply_text("💚 **Revived!** Welcome back!")
            return
        else:
            await update.message.reply_text("✅ You're already alive!")
            return
    await update.message.reply_text(f"✅ Bought **{name}**!", parse_mode=ParseMode.MARKDOWN)

async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db.get_user(update.effective_user.id)
    txt = f"🎒 **Inventory**\n\n🛡️ Shield: {'✅' if u['shield'] else '❌'}\n👑 Premium: {'✅' if u['premium'] else '❌'}\n🐾 Pet: {u['pet'] or 'None'}\n💀 Status: {'Dead 💀' if db.is_dead(update.effective_user.id) else 'Alive ✅'}\n💎 Subscriber: {'✅' if has_subscription(update.effective_user.id) else '❌'}"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = db.get_user(uid)
    if u['coins'] < 5000:
        await update.message.reply_text("❌ Subscription costs 5,000 coins! You need more coins!")
        return
    db.add_coins(uid, -5000)
    expiry = (datetime.now() + timedelta(days=30)).isoformat()
    db.execute("INSERT OR REPLACE INTO subscriptions (uid, expiry) VALUES (?, ?)", (uid, expiry))
    await update.message.reply_text("💎 **You're now a subscriber!** 🎉\n✨ Benefits: 2-day shield, priority support, and more!")

async def cmd_loan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/loan <amount>` (Max: 5000)")
        return
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid!")
        return
    if amount < 100:
        await update.message.reply_text("❌ Minimum loan: 100 coins!")
        return
    if amount > 5000:
        await update.message.reply_text("❌ Maximum loan: 5,000 coins!")
        return
    u = db.get_user(update.effective_user.id)
    loan_check = db.fetchone("SELECT id FROM transactions WHERE uid = ? AND type = 'loan' AND date > datetime('now', '-7 days')", (update.effective_user.id,))
    if loan_check:
        await update.message.reply_text("❌ You have an active loan!")
        return
    db.add_coins(update.effective_user.id, amount)
    db.execute("INSERT INTO transactions (uid, type, amount, note, date) VALUES (?, ?, ?, ?, ?)", (update.effective_user.id, "loan", amount, f"Loan of {amount}", datetime.now().isoformat()))
    await update.message.reply_text(f"🏦 Loan of **{amount:,}** coins approved! Pay back within 7 days!", parse_mode=ParseMode.MARKDOWN)

async def cmd_invest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/invest <amount>`")
        return
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid!")
        return
    if amount < 100:
        await update.message.reply_text("❌ Minimum investment: 100 coins!")
        return
    u = db.get_user(update.effective_user.id)
    if amount > u['bank']:
        await update.message.reply_text("❌ Not enough in bank!")
        return
    roi = random.uniform(0.5, 2.0)
    returns = int(amount * roi)
    db.update_user(update.effective_user.id, bank=u['bank'] - amount)
    db.add_coins(update.effective_user.id, returns)
    await update.message.reply_text(f"📈 Invested **{amount:,}**!\nReturn: **{returns:,}** ({roi:.2f}x)", parse_mode=ParseMode.MARKDOWN)

async def cmd_addcoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ Owner only!")
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: `/addcoins <@user or id> <amount>`")
        return
    try:
        target = context.args[0]
        amount = int(context.args[1])
        if target.startswith("@"):
            # Find user by username
            users = db.fetchall("SELECT uid FROM users WHERE username = ?", (target[1:],))
            if not users:
                await update.message.reply_text("❌ User not found!")
                return
            uid = users[0][0]
        else:
            uid = int(target)
        db.add_coins(uid, amount)
        await update.message.reply_text(f"✅ Added **{amount:,}** coins to user!", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ═══════════════════════════════════════════════════════════════
#  GAMES (Dice, Mines, Aviator, Blackjack, etc.)
# ═══════════════════════════════════════════════════════════════
async def cmd_dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/dice <bet>`\nExample: `/dice 100`")
        return
    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid bet!")
        return
    if bet < 10:
        await update.message.reply_text("❌ Minimum bet: 10 coins!")
        return
    u = db.get_user(update.effective_user.id)
    if bet > u['coins']:
        await update.message.reply_text("❌ Not enough coins!")
        return
    # Send dice
    result = await context.bot.send_dice(chat_id=update.effective_chat.id, emoji="🎲")
    value = result.dice.value
    if value >= 5:
        commission = int(bet * 0.1) if bet > 100 else int(bet * 0.05)
        win_amount = bet * (value / 3)
        payout = int(win_amount) - commission
        db.add_coins(update.effective_user.id, payout)
        await update.message.reply_text(f"🎲 **You rolled {value}!** 🎉\nWin: {payout:,} coins (Commission: {commission})", parse_mode=ParseMode.MARKDOWN)
    else:
        db.add_coins(update.effective_user.id, -bet)
        await update.message.reply_text(f"🎲 **You rolled {value}!** 😢\nLost: {bet:,} coins", parse_mode=ParseMode.MARKDOWN)

async def cmd_mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/mines <bet>`")
        return
    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid bet!")
        return
    if bet < 10:
        await update.message.reply_text("❌ Minimum bet: 10 coins!")
        return
    u = db.get_user(update.effective_user.id)
    if bet > u['coins']:
        await update.message.reply_text("❌ Not enough coins!")
        return
    mines = random.sample(range(1, 26), 5)
    guess = random.randint(1, 25)
    if guess in mines:
        db.add_coins(update.effective_user.id, -bet)
        await update.message.reply_text(f"💣 **BOOM!** You hit a mine at {guess}!\nLost: {bet:,} coins", parse_mode=ParseMode.MARKDOWN)
    else:
        win = bet * 2
        db.add_coins(update.effective_user.id, win)
        await update.message.reply_text(f"💰 **Safe!** You avoided mines!\nWon: {win:,} coins", parse_mode=ParseMode.MARKDOWN)

async def cmd_aviator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/aviator <bet>`")
        return
    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid bet!")
        return
    if bet < 10:
        await update.message.reply_text("❌ Minimum bet: 10 coins!")
        return
    u = db.get_user(update.effective_user.id)
    if bet > u['coins']:
        await update.message.reply_text("❌ Not enough coins!")
        return
    multiplier = round(random.uniform(1.0, 5.0), 2)
    if random.random() < 0.3:
        db.add_coins(update.effective_user.id, -bet)
        await update.message.reply_text(f"🚀 **Crashed at {multiplier}x!**\nLost: {bet:,} coins", parse_mode=ParseMode.MARKDOWN)
    else:
        win = int(bet * multiplier)
        db.add_coins(update.effective_user.id, win)
        await update.message.reply_text(f"✈️ **Flew to {multiplier}x!**\nWon: {win:,} coins", parse_mode=ParseMode.MARKDOWN)

async def cmd_blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/blackjack <bet>`")
        return
    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid bet!")
        return
    if bet < 10:
        await update.message.reply_text("❌ Minimum bet: 10 coins!")
        return
    u = db.get_user(update.effective_user.id)
    if bet > u['coins']:
        await update.message.reply_text("❌ Not enough coins!")
        return
    player = [random.randint(2, 11), random.randint(2, 11)]
    dealer = [random.randint(2, 11), random.randint(2, 11)]
    def hand_value(hand):
        v = sum(hand)
        if v > 21 and 11 in hand:
            v -= 10
        return v
    ACTIVE_GAMES[update.effective_user.id] = {"type": "bj", "bet": bet, "player": player, "dealer": dealer}
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🃏 Hit", callback_data="bj_hit"),
         InlineKeyboardButton("🛑 Stand", callback_data="bj_stand")]
    ])
    await update.message.reply_text(
        f"🃏 **Blackjack** — Bet: {bet:,}\n\nYour hand: {player} = {hand_value(player)}\nDealer: [{dealer[0]}, ?]",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_rps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✊ Rock", callback_data="rps_rock"),
         InlineKeyboardButton("✋ Paper", callback_data="rps_paper"),
         InlineKeyboardButton("✌️ Scissors", callback_data="rps_scissors")]
    ])
    await update.message.reply_text("✊✋✌️ **Rock Paper Scissors**\nChoose!", reply_markup=kb)

async def cmd_ttt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to challenge!")
        return
    target = update.message.reply_to_message.from_user
    if target.id == update.effective_user.id:
        await update.message.reply_text("😂 Can't play with yourself!")
        return
    cid = update.effective_chat.id
    gid = f"ttt_{cid}"
    ACTIVE_GAMES[gid] = {"type": "ttt", "board": [" "] * 9, "turn": update.effective_user.id, "players": [update.effective_user.id, target.id]}
    await update.message.reply_text(f"❌⭕ **Tic Tac Toe**\n{mention(update.effective_user)} vs {mention(target)}!\nX goes first!", parse_mode=ParseMode.MARKDOWN)
    await send_ttt_board(update, context, gid)

async def send_ttt_board(update_or_query, context, gid):
    g = ACTIVE_GAMES.get(gid)
    if not g:
        return
    board = g["board"]
    kb = []
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            idx = i + j
            cell = board[idx] if board[idx] != " " else "⬜"
            row.append(InlineKeyboardButton(cell, callback_data=f"ttt_{idx}"))
        kb.append(row)
    markup = InlineKeyboardMarkup(kb)
    if hasattr(update_or_query, 'message'):
        await update_or_query.message.reply_text("❌⭕ **Your turn!**", reply_markup=markup)
    else:
        try:
            await update_or_query.edit_message_text("❌⭕ **Your turn!**", reply_markup=markup)
        except:
            pass

async def cmd_trivia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid in ACTIVE_GAMES:
        await update.message.reply_text("A game is already running!")
        return
    questions = [
        {"q": "What is the capital of France?", "a": "Paris", "opts": ["Paris", "London", "Berlin", "Madrid"]},
        {"q": "How many balls in one over in cricket?", "a": "6", "opts": ["4", "5", "6", "8"]},
        {"q": "Who created Python?", "a": "Guido van Rossum", "opts": ["James", "Guido", "Dennis", "Bjarne"]},
        {"q": "What is the largest ocean?", "a": "Pacific", "opts": ["Atlantic", "Indian", "Pacific", "Arctic"]},
        {"q": "What is the chemical formula of water?", "a": "H2O", "opts": ["H2O", "CO2", "O2", "NaCl"]},
    ]
    q = random.choice(questions)
    ACTIVE_GAMES[cid] = {"type": "trivia", "q": q, "answered": False}
    opts = q["opts"][:]
    random.shuffle(opts)
    kb = [[InlineKeyboardButton(opt, callback_data=f"trivia_{opt}")] for opt in opts]
    markup = InlineKeyboardMarkup(kb)
    await update.message.reply_text(f"🧠 **Trivia**\n\n{q['q']}\n\nYou have 20 seconds!", reply_markup=markup)
    await asyncio.sleep(20)
    if cid in ACTIVE_GAMES and not ACTIVE_GAMES[cid].get("answered"):
        await update.message.reply_text(f"⏰ Time's up! Answer: **{q['a']}**", parse_mode=ParseMode.MARKDOWN)
        del ACTIVE_GAMES[cid]

async def cmd_wordbomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid in ACTIVE_GAMES:
        await update.message.reply_text("A game is already running!")
        return
    words = ["apple", "banana", "cherry", "grape", "lemon", "mango", "orange", "peach", "strawberry", "watermelon"]
    word = random.choice(words)
    scrambled = "".join(random.sample(word, len(word)))
    ACTIVE_GAMES[cid] = {"type": "wordbomb", "word": word}
    await update.message.reply_text(f"💣 **Word Bomb**\n\nUnscramble: **{scrambled.upper()}**\n\nYou have 20 seconds!", parse_mode=ParseMode.MARKDOWN)
    await asyncio.sleep(20)
    if cid in ACTIVE_GAMES and ACTIVE_GAMES[cid].get("type") == "wordbomb":
        await update.message.reply_text(f"💥 Time's up! Word was: **{word}**", parse_mode=ParseMode.MARKDOWN)
        del ACTIVE_GAMES[cid]

async def cmd_war(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to challenge!")
        return
    target = update.message.reply_to_message.from_user
    if target.id == update.effective_user.id:
        await update.message.reply_text("😂 Can't challenge yourself!")
        return
    p1 = random.randint(1, 100)
    p2 = random.randint(1, 100)
    u1 = db.get_user(update.effective_user.id)
    u2 = db.get_user(target.id)
    if p1 > p2:
        db.add_coins(update.effective_user.id, 300)
        db.update_user(update.effective_user.id, wins=u1['wins'] + 1)
        db.update_user(target.id, losses=u2['losses'] + 1)
        winner = update.effective_user
    elif p2 > p1:
        db.add_coins(target.id, 300)
        db.update_user(target.id, wins=u2['wins'] + 1)
        db.update_user(update.effective_user.id, losses=u1['losses'] + 1)
        winner = target
    else:
        await update.message.reply_text(f"⚔️ **Draw!** Both scored {p1}!")
        return
    await update.message.reply_text(f"⚔️ **War!**\n\n{mention(update.effective_user)}: {p1}\n{mention(target)}: {p2}\n\n🏆 **{mention(winner)} wins!** +300 coins!", parse_mode=ParseMode.MARKDOWN)

async def cmd_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/bet <amount>` (Win chance: 45%)")
        return
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid!")
        return
    if amount < 10:
        await update.message.reply_text("❌ Minimum bet: 10 coins!")
        return
    u = db.get_user(update.effective_user.id)
    if amount > u['coins']:
        await update.message.reply_text("❌ Not enough coins!")
        return
    if random.random() < 0.45:
        db.add_coins(update.effective_user.id, amount)
        db.update_user(update.effective_user.id, wins=u['wins'] + 1)
        await update.message.reply_text(f"🎲 **You won!** +{amount:,} coins! 🎉", parse_mode=ParseMode.MARKDOWN)
    else:
        db.add_coins(update.effective_user.id, -amount)
        db.update_user(update.effective_user.id, losses=u['losses'] + 1)
        await update.message.reply_text(f"🎲 **You lost!** -{amount:,} coins! 😢", parse_mode=ParseMode.MARKDOWN)

async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/slots <bet>`")
        return
    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid!")
        return
    if bet < 10:
        await update.message.reply_text("❌ Minimum bet: 10 coins!")
        return
    u = db.get_user(update.effective_user.id)
    if bet > u['coins']:
        await update.message.reply_text("❌ Not enough coins!")
        return
    symbols = ["🍒", "🍋", "🍇", "💎", "7️⃣", "🎰"]
    a, b, c = random.choice(symbols), random.choice(symbols), random.choice(symbols)
    if a == b == c:
        win = {"🍒": 500, "🍋": 600, "🍇": 700, "💎": 2000, "7️⃣": 5000, "🎰": 10000}[a]
        payout = bet * win // 100
        db.add_coins(update.effective_user.id, payout)
        await update.message.reply_text(f"🎰 | {a} | {b} | {c} |\n\n🎉 **JACKPOT!** +{payout:,} coins!", parse_mode=ParseMode.MARKDOWN)
    elif a == b or b == c or a == c:
        payout = bet * 2
        db.add_coins(update.effective_user.id, payout)
        await update.message.reply_text(f"🎰 | {a} | {b} | {c} |\n\n✨ Win! +{payout:,} coins!", parse_mode=ParseMode.MARKDOWN)
    else:
        db.add_coins(update.effective_user.id, -bet)
        await update.message.reply_text(f"🎰 | {a} | {b} | {c} |\n\n😢 Lost {bet:,} coins!", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to ban!")
        return
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.ban_member(target.id)
        await update.message.reply_text(f"🔨 **Banned** {mention(target)}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/unban <user_id>`")
        return
    try:
        uid = int(context.args[0])
        await update.effective_chat.unban_member(uid)
        await update.message.reply_text("✅ **Unbanned!**", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to mute!")
        return
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.restrict_member(target.id, permissions={"can_send_messages": False})
        await update.message.reply_text(f"🔇 **Muted** {mention(target)}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to unmute!")
        return
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.restrict_member(target.id, permissions={
            "can_send_messages": True,
            "can_send_media_messages": True,
            "can_send_polls": True,
            "can_send_other_messages": True
        })
        await update.message.reply_text(f"🔊 **Unmuted** {mention(target)}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to kick!")
        return
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.ban_member(target.id)
        await update.effective_chat.unban_member(target.id)
        await update.message.reply_text(f"👢 **Kicked** {mention(target)}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to warn!")
        return
    target = update.message.reply_to_message.from_user
    reason = " ".join(context.args) or "No reason"
    db.execute("INSERT INTO warnings (uid, cid, reason, warned_by, date) VALUES (?, ?, ?, ?, ?)", (target.id, update.effective_chat.id, reason, update.effective_user.id, datetime.now().isoformat()))
    await update.message.reply_text(f"⚠️ **Warned** {mention(target)}\nReason: {reason}", parse_mode=ParseMode.MARKDOWN)

async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a message to purge from!")
        return
    try:
        target_msg = update.message.reply_to_message.message_id
        current_msg = update.message.message_id
        messages = list(range(target_msg, current_msg + 1))
        if len(messages) > 100:
            await update.message.reply_text("⚠️ Can only delete up to 100 messages!")
            return
        await update.effective_chat.delete_messages(messages)
        await update.message.reply_text(f"🧹 **Purged** {len(messages)} messages!", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_tagall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    try:
        members = []
        async for member in context.bot.get_chat_members(update.effective_chat.id):
            if not member.user.is_bot:
                members.append(f"[{member.user.first_name}](tg://user?id={member.user.id})")
        if not members:
            await update.message.reply_text("No members found!")
            return
        text = "📢 **Attention everyone!**\n\n" + " ".join(members[:30])
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/setwelcome Welcome message!`")
        return
    text = " ".join(context.args)
    db.execute("INSERT OR REPLACE INTO chat_settings (cid, welcome) VALUES (?, ?)", (update.effective_chat.id, text))
    await update.message.reply_text("✅ Welcome message set!")

async def cmd_setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/setgoodbye Goodbye message!`")
        return
    text = " ".join(context.args)
    db.execute("INSERT OR REPLACE INTO chat_settings (cid, goodbye) VALUES (?, ?)", (update.effective_chat.id, text))
    await update.message.reply_text("✅ Goodbye message set!")

# ═══════════════════════════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════════════════════════
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    msg = await update.message.reply_text("🏓 Pong...")
    ms = int((time.time() - start) * 1000)
    await msg.edit_text(f"🏓 **Pong!** `{ms}ms`", parse_mode=ParseMode.MARKDOWN)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.fetchone("SELECT COUNT(*) FROM users")[0]
    groups = db.fetchone("SELECT COUNT(*) FROM chat_settings")[0]
    await update.message.reply_text(f"📊 **Stats**\n👤 Users: `{users}`\n💬 Groups: `{groups}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"ℹ️ **Info**\n🆔 ID: `{user.id}`\n👤 Name: {user.first_name}", parse_mode=ParseMode.MARKDOWN)

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Your ID: `{update.effective_user.id}`")

async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/weather <city>`")
        return
    await update.message.reply_text("🌤️ *Weather API coming soon!*", parse_mode=ParseMode.MARKDOWN)

async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 *News API coming soon!*", parse_mode=ParseMode.MARKDOWN)

async def cmd_wiki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/wiki <term>`")
        return
    await update.message.reply_text("📖 *Wikipedia API coming soon!*", parse_mode=ParseMode.MARKDOWN)

async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/translate <text>`")
        return
    await update.message.reply_text("🌍 *Translation API coming soon!*", parse_mode=ParseMode.MARKDOWN)

async def cmd_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    password = ''.join(random.choice(chars) for _ in range(16))
    await update.message.reply_text(f"🔐 **Password:** `{password}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🕐 **UTC:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

async def cmd_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 *Crypto API coming soon!*", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════
#  FUN
# ═══════════════════════════════════════════════════════════════
async def cmd_roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_user
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    roasts = [
        f"You're not stupid, {target.first_name}... you just have bad luck thinking.",
        f"{target.first_name}, you're proof that evolution can go in reverse.",
        f"{target.first_name}, you bring everyone so much joy... when you leave.",
        f"Roses are red, violets are blue, {target.first_name} has 5 seconds of screen time.",
        f"{target.first_name}, you're like a cloud. When you disappear, it's a beautiful day."
    ]
    await update.message.reply_text(random.choice(roasts))

async def cmd_compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_user
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    compliments = [
        f"{target.first_name}, you're amazing! 😊",
        f"{target.first_name}, you have a beautiful soul! 💕",
        f"{target.first_name}, you're one of a kind! ⭐",
        f"{target.first_name}, your energy is infectious! 🔥",
        f"{target.first_name}, you make the world brighter! 🌈"
    ]
    await update.message.reply_text(random.choice(compliments))

async def cmd_8ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/8ball <question>`")
        return
    answers = [
        "🎱 Yes, definitely!", "🎱 No, absolutely not!", "🎱 Maybe, ask again.",
        "🎱 It is certain!", "🎱 Cannot predict now.", "🎱 Concentrate and ask again.",
        "🎱 Don't count on it.", "🎱 Outlook good!", "🎱 My sources say no.",
        "🎱 Signs point to yes.", "🎱 Very doubtful.", "🎱 Without a doubt."
    ]
    await update.message.reply_text(random.choice(answers))

async def cmd_horoscope(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/horoscope <zodiac>`")
        return
    zodiac = context.args[0].lower()
    horoscopes = [
        "Today is your lucky day! 🍀", "Be cautious with finances 💰",
        "Love is in the air! ❤️", "Focus on your goals 🎯",
        "A surprise awaits you! 🎉", "Take a break and relax 🧘"
    ]
    await update.message.reply_text(f"♈ **{zodiac.upper()}**\n\n{random.choice(horoscopes)}")

async def cmd_lovecalc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to calculate love!")
        return
    target = update.message.reply_to_message.from_user
    score = random.randint(0, 100)
    if score >= 80:
        result = "❤️ Perfect match!"
    elif score >= 50:
        result = "💕 Good chemistry!"
    else:
        result = "💔 Work on it!"
    await update.message.reply_text(f"💞 **Love Calculator**\n\n{mention(update.effective_user)} ❤️ {mention(target)}\n**Score:** {score}%\n{result}", parse_mode=ParseMode.MARKDOWN)

async def cmd_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memes = [
        "https://imgflip.com/gif/52k7g2",
        "https://imgflip.com/gif/52k7ge",
        "https://imgflip.com/gif/52k7gm"
    ]
    await update.message.reply_text(f"🖼️ **Meme:**\n{random.choice(memes)}", parse_mode=ParseMode.MARKDOWN)

async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "Be the change you wish to see in the world. — Gandhi",
        "In the middle of difficulty lies opportunity. — Einstein",
        "The only way to do great work is to love what you do. — Jobs",
        "Life is what happens when you're busy making other plans. — Lennon",
        "Success is not final, failure is not fatal. — Churchill"
    ]
    await update.message.reply_text(f"📜 **Quote:**\n\n_{random.choice(quotes)}_", parse_mode=ParseMode.MARKDOWN)

async def cmd_riddle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    riddles = [
        ("What has a face but no head, hands but no arms?", "A clock"),
        ("What can travel around the world while staying in a corner?", "A stamp"),
        ("What gets wetter the more it dries?", "A towel"),
        ("What has keys but no locks?", "A piano")
    ]
    q, a = random.choice(riddles)
    await update.message.reply_text(f"🧩 **Riddle:**\n{q}\n\n_Think about it!_", parse_mode=ParseMode.MARKDOWN)

async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Why don't scientists trust atoms? Because they make up everything! 😂",
        "What do you call a fake noodle? An impasta! 🍝",
        "Why did the scarecrow win an award? Outstanding in his field! 🌾",
        "I told my computer I needed a break, now it sends me Kit-Kats! 🍫",
        "What's orange and sounds like a parrot? A carrot! 🥕"
    ]
    await update.message.reply_text(random.choice(jokes))

async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = [
        "Honey never spoils! 3000-year-old honey is still edible! 🍯",
        "Octopuses have three hearts! 🐙",
        "Bananas are berries, but strawberries aren't! 🍌",
        "A day on Venus is longer than a year on Venus! 🌍",
        "The total weight of all ants on Earth equals all humans! 🐜"
    ]
    await update.message.reply_text(f"🧠 **Fact:**\n\n{random.choice(facts)}", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════
#  NOTES & TODOS
# ═══════════════════════════════════════════════════════════════
async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: `/save <name> <content>`")
        return
    name = context.args[0]
    content = " ".join(context.args[1:])
    db.execute("INSERT OR REPLACE INTO notes (cid, name, content) VALUES (?, ?, ?)", (update.effective_chat.id, name, content))
    await update.message.reply_text(f"📝 **Saved:** `{name}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_get(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/get <name>`")
        return
    name = context.args[0]
    note = db.fetchone("SELECT content FROM notes WHERE cid = ? AND name = ?", (update.effective_chat.id, name))
    if note:
        await update.message.reply_text(f"📝 **{name}:**\n\n{note[0]}", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Note not found!")

async def cmd_listnotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = db.fetchall("SELECT name FROM notes WHERE cid = ?", (update.effective_chat.id,))
    if not notes:
        await update.message.reply_text("📭 No notes saved!")
        return
    txt = "📝 **Notes**\n\n"
    for note in notes:
        txt += f"• `{note[0]}`\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/todo <task>`")
        return
    task = " ".join(context.args)
    db.execute("INSERT INTO todos (uid, task) VALUES (?, ?)", (update.effective_user.id, task))
    await update.message.reply_text(f"✅ **Todo added:** {task}")

async def cmd_todolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    todos = db.fetchall("SELECT id, task, done FROM todos WHERE uid = ? ORDER BY id", (update.effective_user.id,))
    if not todos:
        await update.message.reply_text("📭 No todos!")
        return
    txt = "📋 **Todos**\n\n"
    for todo in todos:
        status = "✅" if todo[2] else "⏳"
        txt += f"{status} `{todo[1]}` — `/done {todo[0]}`\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/done <todo_id>`")
        return
    try:
        tid = int(context.args[0])
        db.execute("UPDATE todos SET done = 1 WHERE id = ? AND uid = ?", (tid, update.effective_user.id))
        await update.message.reply_text("✅ **Todo completed!**")
    except:
        await update.message.reply_text("❌ Invalid todo ID!")

# ═══════════════════════════════════════════════════════════════
#  WEB GAMES
# ═══════════════════════════════════════════════════════════════
async def cmd_wav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Play Aviator", url="https://t.me/gamee?game=Aviator")]])
    await update.message.reply_text("🚀 **Web Aviator**", reply_markup=kb)

async def cmd_wludo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎲 Play Ludo", url="https://t.me/gamee?game=Ludo")]])
    await update.message.reply_text("🎲 **Web Ludo**", reply_markup=kb)

async def cmd_wmines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💎 Play Mines", url="https://t.me/gamee?game=Mines")]])
    await update.message.reply_text("💎 **Web Mines**", reply_markup=kb)

async def cmd_wspin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Play Spin", url="https://t.me/gamee?game=SlotMachine")]])
    await update.message.reply_text("🎰 **Web Spin**", reply_markup=kb)

# ═══════════════════════════════════════════════════════════════
#  CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    
    if data == "profile":
        await cmd_profile(update, context)
        return
    if data == "daily":
        await cmd_daily(update, context)
        return
    
    if data.startswith("marry_yes_"):
        proposer = int(data.split("_")[2])
        if uid != proposer:
            existing = db.fetchone("SELECT * FROM marriages WHERE user1 = ? OR user2 = ?", (uid, uid))
            if existing:
                await query.edit_message_text("💔 You're already married!")
                return
            db.execute("INSERT INTO marriages (user1, user2, married_date) VALUES (?, ?, ?)", (proposer, uid, datetime.now().isoformat()))
            db.update_user(proposer, married_to=uid)
            db.update_user(uid, married_to=proposer)
            await query.edit_message_text(f"💍 **Congratulations!**\n\n{mention(query.from_user)} accepted!\n\nYou are now married! ❤️", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("😂 Can't marry yourself!")
        return
    
    if data.startswith("marry_no_"):
        await query.edit_message_text(f"💔 {mention(query.from_user)} rejected...", parse_mode=ParseMode.MARKDOWN)
        return
    
    # Blackjack
    if data == "bj_hit":
        if uid not in ACTIVE_GAMES or ACTIVE_GAMES[uid].get("type") != "bj":
            return
        game = ACTIVE_GAMES[uid]
        game["player"].append(random.randint(2, 11))
        def hand_value(hand):
            v = sum(hand)
            if v > 21 and 11 in hand:
                v -= 10
            return v
        pv = hand_value(game["player"])
        if pv > 21:
            db.add_coins(uid, -game["bet"])
            u = db.get_user(uid)
            db.update_user(uid, losses=u['losses'] + 1)
            del ACTIVE_GAMES[uid]
            await query.edit_message_text(f"🃏 **BUST!** {pv}\nLost **{game['bet']:,}** coins! 💔", parse_mode=ParseMode.MARKDOWN)
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🃏 Hit", callback_data="bj_hit"), InlineKeyboardButton("🛑 Stand", callback_data="bj_stand")]])
            await query.edit_message_text(f"🃏 Your hand: {game['player']} = {pv}\nDealer: [{game['dealer'][0]}, ?]", reply_markup=kb)
        return
    
    if data == "bj_stand":
        if uid not in ACTIVE_GAMES or ACTIVE_GAMES[uid].get("type") != "bj":
            return
        game = ACTIVE_GAMES[uid]
        def hand_value(hand):
            v = sum(hand)
            if v > 21 and 11 in hand:
                v -= 10
            return v
        dv = hand_value(game["dealer"])
        while dv < 17:
            game["dealer"].append(random.randint(2, 11))
            dv = hand_value(game["dealer"])
        pv = hand_value(game["player"])
        u = db.get_user(uid)
        if dv > 21 or pv > dv:
            db.add_coins(uid, game["bet"])
            db.update_user(uid, wins=u['wins'] + 1)
            result = f"🎉 Win! +{game['bet']:,} coins!"
        elif pv < dv:
            db.add_coins(uid, -game["bet"])
            db.update_user(uid, losses=u['losses'] + 1)
            result = f"😢 Dealer wins! -{game['bet']:,} coins!"
        else:
            result = "🤝 Push! Bet returned."
        del ACTIVE_GAMES[uid]
        await query.edit_message_text(f"🃏 **Result**\n\nYou: {pv} {game['player']}\nDealer: {dv} {game['dealer']}\n\n{result}", parse_mode=ParseMode.MARKDOWN)
        return
    
    # RPS
    if data.startswith("rps_"):
        choices = {"rps_rock": "✊ Rock", "rps_paper": "✋ Paper", "rps_scissors": "✌️ Scissors"}
        beats = {"rps_rock": "rps_scissors", "rps_paper": "rps_rock", "rps_scissors": "rps_paper"}
        bot = random.choice(["rps_rock", "rps_paper", "rps_scissors"])
        if data == bot:
            result = "🤝 Draw!"
        elif beats[data] == bot:
            db.add_coins(uid, 100)
            result = "🎉 Win! +100 coins!"
        else:
            db.add_coins(uid, -50)
            result = "😢 Lose! -50 coins!"
        await query.edit_message_text(f"✊✋✌️ **RPS**\n\nYou: {choices[data]}\nBot: {choices[bot]}\n\n{result}", parse_mode=ParseMode.MARKDOWN)
        return
    
    # Trivia
    if data.startswith("trivia_"):
        cid = update.effective_chat.id
        if cid not in ACTIVE_GAMES or ACTIVE_GAMES[cid].get("type") != "trivia":
            return
        game = ACTIVE_GAMES[cid]
        if game.get("answered"):
            return
        answer = data.replace("trivia_", "")
        correct = game["q"]["a"]
        game["answered"] = True
        if answer.lower() == correct.lower():
            db.add_coins(uid, 200)
            db.add_xp(uid, 50)
            u = db.get_user(uid)
            db.update_user(uid, wins=u['wins'] + 1)
            await query.edit_message_text(f"🎉 **Correct!** {answer}\n\n+200 coins! +50 XP!", parse_mode=ParseMode.MARKDOWN)
        else:
            u = db.get_user(uid)
            db.update_user(uid, losses=u['losses'] + 1)
            await query.edit_message_text(f"❌ Wrong! Answer: **{correct}**", parse_mode=ParseMode.MARKDOWN)
        del ACTIVE_GAMES[cid]
        return
    
    # Tic Tac Toe
    if data.startswith("ttt_"):
        cid = update.effective_chat.id
        gid = f"ttt_{cid}"
        if gid not in ACTIVE_GAMES:
            return
        game = ACTIVE_GAMES[gid]
        idx = int(data.split("_")[1])
        if game["turn"] != uid:
            await query.answer("Not your turn!", show_alert=True)
            return
        if game["board"][idx] != " ":
            await query.answer("Already taken!", show_alert=True)
            return
        symbol = "X" if uid == game["players"][0] else "O"
        game["board"][idx] = symbol
        game["turn"] = game["players"][1] if uid == game["players"][0] else game["players"][0]
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        winner = None
        for a, b, c in wins:
            if game["board"][a] == game["board"][b] == game["board"][c] != " ":
                winner = uid
                break
        if winner:
            db.add_coins(uid, 300)
            u = db.get_user(uid)
            db.update_user(uid, wins=u['wins'] + 1)
            await query.edit_message_text(f"🎉 **{query.from_user.first_name} wins!**\n\n{game['board'][:3]}\n{game['board'][3:6]}\n{game['board'][6:]}\n\n+300 coins!", parse_mode=ParseMode.MARKDOWN)
            del ACTIVE_GAMES[gid]
            return
        if " " not in game["board"]:
            await query.edit_message_text(f"🤝 **Draw!**\n\n{game['board'][:3]}\n{game['board'][3:6]}\n{game['board'][6:]}", parse_mode=ParseMode.MARKDOWN)
            del ACTIVE_GAMES[gid]
            return
        await send_ttt_board(query, context, gid)
        return

# ═══════════════════════════════════════════════════════════════
#  MESSAGE HANDLERS
# ═══════════════════════════════════════════════════════════════
async def ai_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    text = update.message.text
    
    # Only respond if mentioned or replied to
    bot_username = context.bot.username.lower()
    is_reply_to_bot = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
    is_mention = f"@{bot_username}" in text.lower()
    
    if not is_reply_to_bot and not is_mention:
        return
    
    # Update message count
    u = db.get_user(user.id)
    db.update_user(user.id, messages=u['messages'] + 1)
    
    # Rate limiting
    if not check_cooldown(user.id, "ai_chat", 5):
        await update.message.reply_text("⏰ Please wait a moment before chatting again!")
        return
    
    # Word bomb
    cid = update.effective_chat.id
    if cid in ACTIVE_GAMES and ACTIVE_GAMES[cid].get("type") == "wordbomb":
        if text.lower() == ACTIVE_GAMES[cid]["word"]:
            db.add_coins(user.id, 500)
            db.add_xp(user.id, 100)
            await update.message.reply_text(f"🎉 **{user.first_name} solved it!** +500 coins! 💣", parse_mode=ParseMode.MARKDOWN)
            del ACTIVE_GAMES[cid]
            return
    
    # AI reply
    reply = await ai_reply(text, user.id)
    await update.message.reply_text(reply)

async def afk_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        u = db.get_user(target.id)
        if u['afk']:
            await update.message.reply_text(f"🌙 {target.first_name} is AFK: *{u['afk_reason']}*", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════
#  ERROR HANDLER
# ═══════════════════════════════════════════════════════════════
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# ═══════════════════════════════════════════════════════════════
#  PREMIUM
# ═══════════════════════════════════════════════════════════════
async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = """👑 **Premium Plan**

💰 **Price:** 10,000 coins

✨ **Benefits:**
• Double daily reward
• Exclusive premium commands
• Priority support
• Custom profile badge
• Access to premium games
• No ads

💎 **Subscribe:** `/subscribe` (5,000 coins for 30 days)
🛡️ **Subscriber bonus:** 2-day shield!

Use `/buy premium` to purchase!"""
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
async def main():
    print("🚀 Starting ULTRA BOT v4.0...")
    print(f"📱 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"💾 Database: {DB_FILE}")
    print(f"🎵 yt-dlp: {'✅' if YTDLP_OK else '❌'}")
    print(f"🎙️ VC: {'✅' if VC_OK else '❌'}")
    print(f"🤖 OpenAI: {'✅' if OPENAI_OK else '❌'}")
    
    await voice.init()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Core
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("id", cmd_id))
    
    # Profile & Social
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("title", cmd_title))
    app.add_handler(CommandHandler("propose", cmd_propose))
    app.add_handler(CommandHandler("divorce", cmd_divorce))
    app.add_handler(CommandHandler("afk", cmd_afk))
    app.add_handler(CommandHandler("karma", cmd_karma))
    app.add_handler(CommandHandler("confess", cmd_confess))
    app.add_handler(CommandHandler("fortune", cmd_fortune))
    app.add_handler(CommandHandler("draw", cmd_draw))
    app.add_handler(CommandHandler("pet", cmd_pet))
    app.add_handler(CommandHandler("crush", cmd_crush))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("top", cmd_top))
    
    # Economy
    app.add_handler(CommandHandler("bal", cmd_bal))
    app.add_handler(CommandHandler("bank", cmd_bank))
    app.add_handler(CommandHandler("deposit", cmd_deposit))
    app.add_handler(CommandHandler("withdraw", cmd_withdraw))
    app.add_handler(CommandHandler("transfer", cmd_transfer))
    app.add_handler(CommandHandler("gift", cmd_gift))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("weekly", cmd_weekly))
    app.add_handler(CommandHandler("rob", cmd_rob))
    app.add_handler(CommandHandler("kill", cmd_kill))
    app.add_handler(CommandHandler("revive", cmd_revive))
    app.add_handler(CommandHandler("protect", cmd_protect))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("inventory", cmd_inventory))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("loan", cmd_loan))
    app.add_handler(CommandHandler("invest", cmd_invest))
    app.add_handler(CommandHandler("addcoins", cmd_addcoins))
    
    # Games
    app.add_handler(CommandHandler("dice", cmd_dice_game))
    app.add_handler(CommandHandler("mines", cmd_mines))
    app.add_handler(CommandHandler("aviator", cmd_aviator))
    app.add_handler(CommandHandler("blackjack", cmd_blackjack))
    app.add_handler(CommandHandler("rps", cmd_rps))
    app.add_handler(CommandHandler("ttt", cmd_ttt))
    app.add_handler(CommandHandler("trivia", cmd_trivia))
    app.add_handler(CommandHandler("wordbomb", cmd_wordbomb))
    app.add_handler(CommandHandler("war", cmd_war))
    app.add_handler(CommandHandler("bet", cmd_bet))
    app.add_handler(CommandHandler("slots", cmd_slots))
    
    # Music
    app.add_handler(CommandHandler("play", cmd_play))
    app.add_handler(CommandHandler("vplay", cmd_vplay))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("skip", cmd_skip))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("loop", cmd_loop))
    app.add_handler(CommandHandler("shuffle", cmd_shuffle))
    app.add_handler(CommandHandler("volume", cmd_volume))
    app.add_handler(CommandHandler("vc", cmd_vc))
    app.add_handler(CommandHandler("join", cmd_join))
    app.add_handler(CommandHandler("leave", cmd_leave))
    app.add_handler(CommandHandler("lyrics", cmd_lyrics))
    app.add_handler(CommandHandler("musicadmin", cmd_musicadmin))
    
    # Admin
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("kick", cmd_kick))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("purge", cmd_purge))
    app.add_handler(CommandHandler("tagall", cmd_tagall))
    app.add_handler(CommandHandler("setwelcome", cmd_setwelcome))
    app.add_handler(CommandHandler("setgoodbye", cmd_setgoodbye))
    
    # Utility
    app.add_handler(CommandHandler("weather", cmd_weather))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("wiki", cmd_wiki))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(CommandHandler("password", cmd_password))
    app.add_handler(CommandHandler("timezone", cmd_timezone))
    app.add_handler(CommandHandler("crypto", cmd_crypto))
    
    # Fun
    app.add_handler(CommandHandler("roast", cmd_roast))
    app.add_handler(CommandHandler("compliment", cmd_compliment))
    app.add_handler(CommandHandler("8ball", cmd_8ball))
    app.add_handler(CommandHandler("horoscope", cmd_horoscope))
    app.add_handler(CommandHandler("lovecalc", cmd_lovecalc))
    app.add_handler(CommandHandler("meme", cmd_meme))
    app.add_handler(CommandHandler("quote", cmd_quote))
    app.add_handler(CommandHandler("riddle", cmd_riddle))
    app.add_handler(CommandHandler("joke", cmd_joke))
    app.add_handler(CommandHandler("fact", cmd_fact))
    
    # Notes & Todos
    app.add_handler(CommandHandler("save", cmd_save))
    app.add_handler(CommandHandler("get", cmd_get))
    app.add_handler(CommandHandler("listnotes", cmd_listnotes))
    app.add_handler(CommandHandler("todo", cmd_todo))
    app.add_handler(CommandHandler("todolist", cmd_todolist))
    app.add_handler(CommandHandler("done", cmd_done))
    
    # Web Games
    app.add_handler(CommandHandler("wav", cmd_wav))
    app.add_handler(CommandHandler("wludo", cmd_wludo))
    app.add_handler(CommandHandler("wmines", cmd_wmines))
    app.add_handler(CommandHandler("wspin", cmd_wspin))
    
    # Premium
    app.add_handler(CommandHandler("premium", cmd_premium))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, afk_handler))
    
    app.add_error_handler(error_handler)
    
    print("✅ Bot is running!")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
