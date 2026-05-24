import os
import sqlite3
import logging
from datetime import datetime, timedelta, time as dtime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          ContextTypes, MessageHandler, filters)

# ================= CONFIGURATION =================
TOKEN = os.getenv("Token","8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "8456901459"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "PrepRoom")

DB_NAME = os.getenv("DB_NAME", "/data/preproom.db")
INDIA_TZ = pytz.timezone("Asia/Kolkata")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PrepRoom")

# ================= EXAM CATEGORIES =================
CATEGORIES = {
    "cat_campus": "🏢 Campus Placements",
    "cat_govt": "📋 Government Exams",
    "cat_medical": "🏥 Medical Entrance",
    "cat_engineering": "🔬 Engineering Entrance",
    "cat_mba": "🎓 MBA / GATE",
    "cat_semester": "📚 Semester / Other",
}

EXAMS = {
    "cat_campus": [
        ("TCS NQT", "exam_TCS NQT"),
        ("Infosys", "exam_Infosys"),
        ("Wipro", "exam_Wipro"),
        ("Capgemini", "exam_Capgemini"),
        ("Accenture", "exam_Accenture"),
        ("Cognizant", "exam_Cognizant"),
        ("Other Campus", "exam_Other Campus"),
    ],
    "cat_govt": [
        ("SSC CGL", "exam_SSC CGL"),
        ("SSC CHSL", "exam_SSC CHSL"),
        ("Banking", "exam_Banking"),
        ("RRB NTPC", "exam_RRB NTPC"),
        ("UPSC", "exam_UPSC"),
        ("State PSC", "exam_State PSC"),
        ("Other Govt", "exam_Other Govt"),
    ],
    "cat_medical": [
        ("NEET", "exam_NEET"),
    ],
    "cat_engineering": [
        ("JEE Mains", "exam_JEE Mains"),
        ("JEE Advanced", "exam_JEE Advanced"),
    ],
    "cat_mba": [
        ("CAT", "exam_CAT"),
        ("GATE", "exam_GATE"),
    ],
    "cat_semester": [
        ("Semester Exams", "exam_Semester Exams"),
        ("Other", "exam_Other"),
    ],
}

STUDY_TIMES = [
    ("🌄 Early Morning (5-8 AM)", "time_Early Morning"),
    ("🌅 Morning (8 AM-12 PM)", "time_Morning"),
    ("☀️ Afternoon (12-4 PM)", "time_Afternoon"),
    ("🌆 Evening (4-8 PM)", "time_Evening"),
    ("🌙 Night (8 PM-12 AM)", "time_Night"),
    ("🌃 Late Night (12-3 AM)", "time_Late Night"),
]

LANGUAGES = [
    ("🇬🇧 English", "lang_English"),
    ("🇮🇳 Hindi", "lang_Hindi"),
    ("🇮🇳 Marathi", "lang_Marathi"),
    ("🇮🇳 Tamil", "lang_Tamil"),
    ("🇮🇳 Telugu", "lang_Telugu"),
    ("🇮🇳 Bengali", "lang_Bengali"),
    ("🇮🇳 Kannada", "lang_Kannada"),
    ("🇮🇳 Malayalam", "lang_Malayalam"),
]

# ================= DATABASE =================
def get_conn():
    return sqlite3.connect(DB_NAME)

def setup_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        exam TEXT,
        study_time TEXT,
        language TEXT,
        streak INTEGER DEFAULT 0,
        last_checkin TEXT,
        reputation INTEGER DEFAULT 40,
        partner_id INTEGER,
        group_id INTEGER,
        matched_at TEXT,
        banned INTEGER DEFAULT 0,
        warnings INTEGER DEFAULT 0,
        referred_by TEXT,
        invite_link_generated INTEGER DEFAULT 0,
        streak_competition_sent INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS waiting_queue (
        user_id INTEGER PRIMARY KEY,
        exam TEXT,
        study_time TEXT,
        language TEXT,
        joined_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS pending_groups (
        match_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER,
        user2_id INTEGER,
        matched_at TEXT,
        pair_type TEXT DEFAULT 'random',
        status TEXT DEFAULT 'pending'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS temp_registration (
        user_id INTEGER PRIMARY KEY,
        exam TEXT,
        study_time TEXT,
        referred_by TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inviter_id INTEGER,
        inviter_username TEXT,
        invited_id INTEGER,
        invited_username TEXT,
        invite_sent_at TEXT,
        joined_at TEXT,
        pair_formed INTEGER DEFAULT 0,
        pair_formed_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        sent_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS blocked_pairs (
        user_id INTEGER,
        blocked_id INTEGER,
        PRIMARY KEY (user_id, blocked_id)
    )""")

    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

def today():
    return datetime.now(INDIA_TZ).date()

def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date() if d else None

def days_missed(last_checkin):
    if not last_checkin:
        return 999
    last = parse_date(last_checkin)
    return (today() - last).days

def get_tier(reputation):
    if reputation >= 90:
        return "💎 Diamond"
    elif reputation >= 75:
        return "🥇 Gold"
    elif reputation >= 50:
        return "🥈 Silver"
    else:
        return "🥉 Bronze"

async def do_match(context, user_id, partner_id,
                   exam, study_time, language,
                   partner_name, partner_username,
                   partner_language, pair_type="random"):
    now = datetime.now(INDIA_TZ).isoformat()
    conn = get_conn()
    c = conn.cursor()

    c.execute("""UPDATE users SET partner_id=?, matched_at=?
                 WHERE user_id=?""", (partner_id, now, user_id))
    c.execute("""UPDATE users SET partner_id=?, matched_at=?
                 WHERE user_id=?""", (user_id, now, partner_id))
    c.execute("DELETE FROM waiting_queue WHERE user_id=?", (partner_id,))
    c.execute("""INSERT INTO pending_groups
                 (user1_id, user2_id, matched_at, pair_type)
                 VALUES (?, ?, ?, ?)""",
              (user_id, partner_id, now, pair_type))
    conn.commit()
    conn.close()

    user_display = f"@{context._user_data.get('username', '')}" \
        if context._user_data.get('username') else "Partner"
    partner_display = f"@{partner_username}" \
        if partner_username else partner_name

    pair_msg = (
        f"🤝 *Partner Match Confirmed!*\n\n"
        f"*{context._user_data.get('first_name', 'You')}* "
        f"↔ *{partner_name}*\n"
        f"📚 Exam: {exam}\n"
        f"⏰ Study Time: {study_time}\n\n"
        f"Tumhara pehla check-in aaj hai.\n"
        f"Koi ek pehle jaao —\n"
        f"*/checkin* bhejo jab ho jaao.\n\n"
        f"Partner ko instant notification milega.\n"
        f"Unhe wait mat karao. 🔥"
    )

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 *You've been matched!*\n\n"
                 f"👥 *Your Study Partner:*\n"
                 f"👤 Name: {partner_name}\n"
                 f"📱 Username: {partner_display}\n"
                 f"📚 Exam: {exam}\n"
                 f"⏰ Study Time: {study_time}\n"
                 f"🗣 Language: {partner_language}\n\n"
                 f"📢 Admin will create your group soon!\n\n"
                 f"• /checkin — Mark daily study\n"
                 f"• /streak — Your stats\n"
                 f"• /partner — Partner details\n"
                 f"• /invite — Invite a friend",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=partner_id,
            text=f"🎉 *You've been matched!*\n\n"
                 f"👥 *Your Study Partner:*\n"
                 f"👤 Name: "
                 f"{context._user_data.get('first_name', 'Partner')}\n"
                 f"📱 Username: {user_display}\n"
                 f"📚 Exam: {exam}\n"
                 f"⏰ Study Time: {study_time}\n"
                 f"🗣 Language: {language}\n\n"
                 f"📢 Admin will create your group soon!\n\n"
                 f"• /checkin — Mark daily study\n"
                 f"• /streak — Your stats\n"
                 f"• /partner — Partner details\n"
                 f"• /invite — Invite a friend",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Match notification failed: {e}")

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT banned FROM users WHERE user_id=?", (user.id,))
    row = c.fetchone()
    conn.close()

    if row and row[0] == 1:
        await update.message.reply_text(
            "🚫 *You have been banned from PrepRoom.*",
            parse_mode="Markdown"
        )
        return

    # Check for referral parameter
    referred_by = None
    inviter_name = None

    if context.args:
        param = context.args[0]
        if param.startswith("REF_"):
            referred_by = param.replace("REF_", "")

            # Find inviter
            conn = get_conn()
            c = conn.cursor()
            c.execute("""SELECT user_id, first_name FROM users
                         WHERE username=?""", (referred_by,))
            inviter = c.fetchone()

            if inviter:
                inviter_id, inviter_name = inviter

                # Log referral
                c.execute("""INSERT OR IGNORE INTO referrals
                    (inviter_id, inviter_username, invited_id,
                     invited_username, invite_sent_at, joined_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (inviter_id, referred_by, user.id,
                     user.username,
                     datetime.now(INDIA_TZ).isoformat(),
                     datetime.now(INDIA_TZ).isoformat()))
                conn.commit()
            conn.close()

    # Store referral in temp
    if referred_by:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO temp_registration
                     (user_id, referred_by) VALUES (?, ?)""",
                  (user.id, referred_by))
        conn.commit()
        conn.close()

    keyboard = [
        [InlineKeyboardButton(
            "🏢 Campus Placements", callback_data="cat_campus")],
        [InlineKeyboardButton(
            "📋 Government Exams", callback_data="cat_govt")],
        [InlineKeyboardButton(
            "🏥 Medical Entrance", callback_data="cat_medical")],
        [InlineKeyboardButton(
            "🔬 Engineering Entrance", callback_data="cat_engineering")],
        [InlineKeyboardButton(
            "🎓 MBA / GATE", callback_data="cat_mba")],
        [InlineKeyboardButton(
            "📚 Semester / Other", callback_data="cat_semester")],
    ]

    if referred_by and inviter_name:
        welcome_msg = (
            f"👋 *{inviter_name} ne tumhe personally invite kiya hai.*\n\n"
            f"Woh already prep kar raha/rahi hai\n"
            f"aur tumhara wait kar raha/rahi hai.\n\n"
            f"Sirf 2 sawaal:\n"
            f"1. Kaun sa exam?\n"
            f"2. Kab padhte ho?\n\n"
            f"Reply karo — abhi match karta hoon. 🔥\n\n"
            f"📚 *Select your exam category:*"
        )
    else:
        welcome_msg = (
            "👋 *Welcome to PrepRoom!*\n\n"
            "I'll match you with a study partner.\n\n"
            "📚 *Select your exam category:*"
        )

    await update.message.reply_text(
        welcome_msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= INVITE COMMAND =================
async def invite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user.username:
        await update.message.reply_text(
            "⚠️ *You need a Telegram username to invite friends.*\n\n"
            "Go to Telegram Settings → set a username → "
            "then try /invite again.",
            parse_mode="Markdown"
        )
        return

    invite_link = f"https://t.me/{BOT_USERNAME}?start=REF_{user.username}"

    conn = get_conn()
    c = conn.cursor()
    c.execute("""UPDATE users SET invite_link_generated=1
                 WHERE user_id=?""", (user.id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🔗 *Tumhara personal invite link:*\n\n"
        f"`{invite_link}`\n\n"
        f"Yeh link sirf tumhare dost ke liye hai.\n"
        f"Woh join karte hi directly\n"
        f"tumse pair ho jaenge.\n\n"
        f"Random stranger nahi. Seedha tumhara partner. 🎯\n\n"
        f"*Share karo aur saath padho!* 💪",
        parse_mode="Markdown"
    )

# ================= BRAG COMMAND =================
async def brag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT first_name, username, streak, reputation,
                 exam, partner_id, last_checkin
                 FROM users WHERE user_id=?""", (user_id,))
    row = c.fetchone()

    if not row:
        await update.message.reply_text(
            "❌ *Not registered!* Use /start first.",
            parse_mode="Markdown")
        conn.close()
        return

    name, username, streak, reputation, exam, \
        partner_id, last_checkin = row

    # Get partner name
    partner_name = "None"
    if partner_id:
        c.execute("SELECT first_name FROM users WHERE user_id=?",
                  (partner_id,))
        p = c.fetchone()
        if p:
            partner_name = p[0]

    # Get total users for percentile
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE streak>=?", (streak,))
    above = c.fetchone()[0]

    # Monthly checkins
    month_start = today().replace(day=1).strftime("%Y-%m-%d")
    c.execute("""SELECT COUNT(*) FROM users
                 WHERE user_id=? AND last_checkin>=?""",
              (user_id, month_start))
    monthly = c.fetchone()[0]
    conn.close()

    tier = get_tier(reputation)
    percentile = max(1, int((1 - above / max(total_users, 1)) * 100))

    await update.message.reply_text(
        f"🔥 *PREP ROOM STATS*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *Name:* {name}\n"
        f"📱 *Username:* @{username or 'Not set'}\n"
        f"🔥 *Streak:* {streak} days\n"
        f"🏆 *Tier:* {tier}\n"
        f"👥 *Partner:* {partner_name}\n"
        f"📚 *Exam:* {exam}\n"
        f"📅 *Check-ins this month:* {monthly}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 *Top {percentile}% of all PrepRoom users!*\n\n"
        f"Share karo —\n"
        f"inspire karo kisi ko aaj. 💪\n\n"
        f"👉 /invite se apne dost ko bulao!",
        parse_mode="Markdown"
    )

# ================= HELP =================
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *PrepRoom Commands*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔰 *Getting Started*\n"
        "• /start — Register or re-register\n"
        "• /help — Show this message\n"
        "• /rules — How PrepRoom works\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 *Daily Actions*\n"
        "• /checkin — Mark today as studied ✅\n"
        "• /streak — View your stats\n"
        "• /profile — View full profile\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 *Partner*\n"
        "• /partner — View partner details\n"
        "• /report — Report inactive partner\n"
        "• /block — Block current partner\n"
        "• /leave — Leave current partner\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 *Referral*\n"
        "• /invite — Get your personal invite link\n"
        "• /brag — Share your stats\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚙️ *Settings*\n"
        "• /edit — Change exam or study time\n"
        "• /feedback — Send feedback to admin\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🏆 *Fun*\n"
        "• /leaderboard — Top 10 by streak\n\n"
        "💪 *Study hard every day!*",
        parse_mode="Markdown"
    )

# ================= PROFILE =================
async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT first_name, username, exam, study_time,
                 language, streak, reputation, last_checkin,
                 partner_id, matched_at, referred_by
                 FROM users WHERE user_id=?""", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(
            "❌ *Not registered!* Use /start first.",
            parse_mode="Markdown")
        return

    name, username, exam, study_time, language, streak, \
        reputation, last_checkin, partner_id, \
        matched_at, referred_by = row

    username_display = f"@{username}" if username else "Not set"
    tier = get_tier(reputation)
    partner_status = "✅ Matched" if partner_id else "⏳ Waiting"
    last = last_checkin if last_checkin else "Never"
    ref_by = f"@{referred_by}" if referred_by else "Direct join"

    await update.message.reply_text(
        f"👤 *Your PrepRoom Profile*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔖 *Name:* {name}\n"
        f"📱 *Username:* {username_display}\n"
        f"🆔 *ID:* `{user_id}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📚 *Exam:* {exam}\n"
        f"⏰ *Study Time:* {study_time}\n"
        f"🗣 *Language:* {language}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔥 *Streak:* {streak} days\n"
        f"⭐ *Reputation:* {reputation}/100\n"
        f"🏆 *Tier:* {tier}\n"
        f"📅 *Last Check-in:* {last}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Partner Status:* {partner_status}\n"
        f"🔗 *Referred by:* {ref_by}",
        parse_mode="Markdown"
    )

# ================= EDIT =================
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(
            "📚 Change Exam", callback_data="edit_exam")],
        [InlineKeyboardButton(
            "⏰ Change Study Time", callback_data="edit_time")],
        [InlineKeyboardButton(
            "🗣 Change Language", callback_data="edit_lang")],
    ]
    await update.message.reply_text(
        "⚙️ *What would you like to change?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= LEAVE =================
async def leave_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row or not row[0]:
        await update.message.reply_text(
            "⏳ *You don't have a partner to leave.*",
            parse_mode="Markdown")
        conn.close()
        return

    partner_id = row[0]
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?",
              (user_id,))
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?",
              (partner_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ *You have left your current partner.*\n\n"
        "Use /start to find a new partner! 💪",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_message(
            chat_id=partner_id,
            text="😔 *Your study partner has left the partnership.*\n\n"
                 "Use /start to find a new partner! 💪",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Leave notification failed: {e}")

# ================= BLOCK =================
async def block_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row or not row[0]:
        await update.message.reply_text(
            "❌ *No partner to block.*",
            parse_mode="Markdown")
        conn.close()
        return

    partner_id = row[0]
    c.execute("""INSERT OR IGNORE INTO blocked_pairs
                 (user_id, blocked_id) VALUES (?, ?)""",
              (user_id, partner_id))
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?",
              (user_id,))
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?",
              (partner_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "🚫 *Partner blocked.*\n\n"
        "Use /start to find a new partner! 💪",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_message(
            chat_id=partner_id,
            text="😔 *Your study partner has ended the partnership.*\n\n"
                 "Use /start to find a new partner! 💪",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Block notification failed: {e}")

# ================= FEEDBACK =================
async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_feedback"] = True
    await update.message.reply_text(
        "💬 *Send your feedback:*\n\n"
        "Type your message and send it now!",
        parse_mode="Markdown"
    )

async def handle_feedback(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_feedback"):
        return

    user = update.effective_user
    message = update.message.text
    context.user_data["waiting_feedback"] = False

    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO feedback (user_id, message, sent_at)
                 VALUES (?, ?, ?)""",
              (user.id, message,
               datetime.now(INDIA_TZ).strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ *Feedback sent! Thank you!* 🙏",
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"💬 *NEW FEEDBACK*\n\n"
             f"👤 *From:* {user.first_name} (ID: `{user.id}`)\n"
             f"📝 *Message:*\n{message}",
        parse_mode="Markdown"
    )

# ================= LEADERBOARD =================
async def leaderboard_cmd(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT first_name, streak, reputation
                 FROM users ORDER BY streak DESC LIMIT 10""")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "⏳ *No data yet!*",
            parse_mode="Markdown")
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣",
              "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    msg = "🏆 *PrepRoom Leaderboard*\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, (name, streak, reputation) in enumerate(rows):
        tier = get_tier(reputation)
        msg += f"{medals[i]} *{name}*\n"
        msg += f"   🔥 {streak} days | {tier}\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "💪 *Keep studying to climb!*"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= BUTTON HANDLER =================
async def button_handler(update: Update,
                         context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == "edit_exam":
        keyboard = [
            [InlineKeyboardButton(
                "🏢 Campus Placements", callback_data="cat_campus")],
            [InlineKeyboardButton(
                "📋 Government Exams", callback_data="cat_govt")],
            [InlineKeyboardButton(
                "🏥 Medical Entrance", callback_data="cat_medical")],
            [InlineKeyboardButton(
                "🔬 Engineering Entrance",
                callback_data="cat_engineering")],
            [InlineKeyboardButton(
                "🎓 MBA / GATE", callback_data="cat_mba")],
            [InlineKeyboardButton(
                "📚 Semester / Other", callback_data="cat_semester")],
        ]
        await query.edit_message_text(
            "📚 *Select your new exam category:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    elif data == "edit_time":
        keyboard = [[InlineKeyboardButton(name, callback_data=cb)]
                    for name, cb in STUDY_TIMES]
        await query.edit_message_text(
            "⏰ *Select your new study time:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    elif data == "edit_lang":
        keyboard = [[InlineKeyboardButton(name, callback_data=cb)]
                    for name, cb in LANGUAGES]
        await query.edit_message_text(
            "🗣 *Select your new language:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if data.startswith("cat_"):
        exams = EXAMS.get(data, [])
        keyboard = [[InlineKeyboardButton(name, callback_data=cb)]
                    for name, cb in exams]
        keyboard.append([InlineKeyboardButton(
            "⬅️ Back", callback_data="back_start")])
        await query.edit_message_text(
            f"✅ *Category:* {CATEGORIES.get(data)}\n\n"
            f"📚 *Select your exam:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "back_start":
        keyboard = [
            [InlineKeyboardButton(
                "🏢 Campus Placements", callback_data="cat_campus")],
            [InlineKeyboardButton(
                "📋 Government Exams", callback_data="cat_govt")],
            [InlineKeyboardButton(
                "🏥 Medical Entrance", callback_data="cat_medical")],
            [InlineKeyboardButton(
                "🔬 Engineering Entrance",
                callback_data="cat_engineering")],
            [InlineKeyboardButton(
                "🎓 MBA / GATE", callback_data="cat_mba")],
            [InlineKeyboardButton(
                "📚 Semester / Other", callback_data="cat_semester")],
        ]
        await query.edit_message_text(
            "📚 *Select your exam category:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("exam_"):
        exam = data.replace("exam_", "")
        conn = get_conn()
        c = conn.cursor()
        c.execute("""UPDATE temp_registration SET exam=?
                     WHERE user_id=?""", (exam, user.id))
        if conn.execute(
                "SELECT changes()").fetchone()[0] == 0:
            c.execute("""INSERT OR REPLACE INTO temp_registration
                         (user_id, exam) VALUES (?, ?)""",
                      (user.id, exam))
        conn.commit()
        conn.close()

        keyboard = [[InlineKeyboardButton(name, callback_data=cb)]
                    for name, cb in STUDY_TIMES]
        await query.edit_message_text(
            f"✅ *Exam:* {exam}\n\n⏰ *When do you usually study?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("time_"):
        study_time = data.replace("time_", "")
        conn = get_conn()
        c = conn.cursor()
        c.execute("""UPDATE temp_registration SET study_time=?
                     WHERE user_id=?""", (study_time, user.id))
        c.execute("""UPDATE users SET study_time=?
                     WHERE user_id=?""", (study_time, user.id))
        conn.commit()
        conn.close()

        keyboard = [[InlineKeyboardButton(name, callback_data=cb)]
                    for name, cb in LANGUAGES]
        await query.edit_message_text(
            f"✅ *Study time:* {study_time}\n\n🗣 *Preferred language?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("lang_"):
        language = data.replace("lang_", "")

        conn = get_conn()
        c = conn.cursor()

        c.execute("""SELECT exam, study_time, referred_by
                     FROM temp_registration WHERE user_id=?""",
                  (user.id,))
        reg = c.fetchone()

        if not reg or not reg[0] or not reg[1]:
            await query.edit_message_text(
                "❌ *Session expired!*\n\nPlease use /start again.",
                parse_mode="Markdown"
            )
            conn.close()
            return

        exam, study_time, referred_by = reg

        c.execute("""INSERT OR REPLACE INTO users
            (user_id, username, first_name, exam, study_time,
             language, referred_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user.id, user.username, user.first_name,
             exam, study_time, language, referred_by))
        conn.commit()

        matched = False

        # Priority 1 — Direct match with inviter
        if referred_by:
            c.execute("""SELECT user_id, first_name, username, language
                         FROM users WHERE username=?
                         AND partner_id IS NULL
                         AND user_id!=?""",
                      (referred_by, user.id))
            inviter_row = c.fetchone()

            if inviter_row:
                inviter_id = inviter_row[0]
                inviter_name = inviter_row[1]
                inviter_username = inviter_row[2]
                inviter_language = inviter_row[3]

                now = datetime.now(INDIA_TZ).isoformat()
                c.execute("""UPDATE users SET partner_id=?, matched_at=?
                             WHERE user_id=?""",
                          (inviter_id, now, user.id))
                c.execute("""UPDATE users SET partner_id=?, matched_at=?
                             WHERE user_id=?""",
                          (user.id, now, inviter_id))
                c.execute("""INSERT INTO pending_groups
                             (user1_id, user2_id, matched_at, pair_type)
                             VALUES (?, ?, ?, 'invited')""",
                          (user.id, inviter_id, now))

                # Update referral record
                c.execute("""UPDATE referrals SET pair_formed=1,
                             pair_formed_at=?
                             WHERE inviter_id=? AND invited_id=?""",
                          (now, inviter_id, user.id))

                c.execute("""DELETE FROM temp_registration
                             WHERE user_id=?""", (user.id,))
                conn.commit()
                conn.close()

                matched = True
                inviter_display = f"@{inviter_username}" \
                    if inviter_username else inviter_name
                user_display = f"@{user.username}" \
                    if user.username else user.first_name

                await query.edit_message_text(
                    f"🎉 *Registration complete!*\n\n"
                    f"✅ *Directly matched with {inviter_name}!*\n\n"
                    f"Your invite link worked! 🎯\n\n"
                    f"Check your messages for details! 👆",
                    parse_mode="Markdown"
                )

                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"🤝 *Partner Match Confirmed!*\n\n"
                         f"*{user.first_name}* ↔ *{inviter_name}*\n"
                         f"📚 Exam: {exam}\n"
                         f"⏰ Study Time: {study_time}\n\n"
                         f"Tumhara pehla check-in aaj hai.\n"
                         f"Koi ek pehle jaao —\n"
                         f"/checkin bhejo jab ho jaao.\n\n"
                         f"Partner ko instant notification milega.\n"
                         f"Unhe wait mat karao. 🔥",
                    parse_mode="Markdown"
                )

                await context.bot.send_message(
                    chat_id=inviter_id,
                    text=f"🤝 *Partner Match Confirmed!*\n\n"
                         f"*{inviter_name}* ↔ *{user.first_name}*\n"
                         f"📚 Exam: {exam}\n"
                         f"⏰ Study Time: {study_time}\n\n"
                         f"Tumhara invite kaam aaya! 🎯\n"
                         f"Tumhara dost join ho gaya!\n\n"
                         f"Koi ek pehle jaao —\n"
                         f"/checkin bhejo jab ho jaao. 🔥",
                    parse_mode="Markdown"
                )

                # Admin notification
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"🎯 *NEW INVITED MATCH!*\n\n"
                         f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                         f"👤 *Inviter:*\n"
                         f"   Name: {inviter_name}\n"
                         f"   Username: {inviter_display}\n"
                         f"   ID: `{inviter_id}`\n\n"
                         f"👤 *Invited:*\n"
                         f"   Name: {user.first_name}\n"
                         f"   Username: {user_display}\n"
                         f"   ID: `{user.id}`\n\n"
                         f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                         f"📚 *Exam:* {exam}\n"
                         f"⏰ *Study Time:* {study_time}\n"
                         f"🔗 *Pair Type:* Invited\n\n"
                         f"✅ *Steps:*\n"
                         f"1️⃣ Create private group\n"
                         f"2️⃣ Add {inviter_display}\n"
                         f"3️⃣ Add {user_display}\n"
                         f"4️⃣ Add bot as admin\n"
                         f"5️⃣ /send_invite {inviter_id} {user.id}",
                    parse_mode="Markdown"
                )

        # Priority 2 — Random match from queue
        if not matched:
            c.execute("""SELECT wq.user_id FROM waiting_queue wq
                         WHERE wq.exam=? AND wq.study_time=?
                         AND wq.user_id!=?
                         AND wq.user_id NOT IN (
                             SELECT blocked_id FROM blocked_pairs
                             WHERE user_id=?
                         )
                         AND ? NOT IN (
                             SELECT blocked_id FROM blocked_pairs
                             WHERE user_id=wq.user_id
                         )
                         LIMIT 1""",
                      (exam, study_time, user.id, user.id, user.id))
            match = c.fetchone()

            if match:
                partner_id = match[0]
                c.execute("""SELECT first_name, username, language
                             FROM users WHERE user_id=?""",
                          (partner_id,))
                partner_row = c.fetchone()
                partner_name = partner_row[0] \
                    if partner_row else "Study Partner"
                partner_username = partner_row[1] if partner_row else None
                partner_language = partner_row[2] \
                    if partner_row else "Unknown"

                now = datetime.now(INDIA_TZ).isoformat()
                c.execute("""UPDATE users SET partner_id=?, matched_at=?
                             WHERE user_id=?""",
                          (partner_id, now, user.id))
                c.execute("""UPDATE users SET partner_id=?, matched_at=?
                             WHERE user_id=?""",
                          (user.id, now, partner_id))
                c.execute("DELETE FROM waiting_queue WHERE user_id=?",
                          (partner_id,))
                c.execute("""INSERT INTO pending_groups
                             (user1_id, user2_id, matched_at, pair_type)
                             VALUES (?, ?, ?, 'random')""",
                          (user.id, partner_id, now))
                c.execute("""DELETE FROM temp_registration
                             WHERE user_id=?""", (user.id,))
                conn.commit()
                conn.close()

                partner_display = f"@{partner_username}" \
                    if partner_username else partner_name
                user_display = f"@{user.username}" \
                    if user.username else user.first_name

                await query.edit_message_text(
                    f"🎉 *Registration complete!*\n\n"
                    f"✅ *Matched with {partner_name}!*\n\n"
                    f"Check messages for details! 👆",
                    parse_mode="Markdown"
                )

                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"🤝 *Partner Match Confirmed!*\n\n"
                         f"*{user.first_name}* ↔ *{partner_name}*\n"
                         f"📚 Exam: {exam}\n"
                         f"⏰ Study Time: {study_time}\n\n"
                         f"Tumhara pehla check-in aaj hai.\n"
                         f"Koi ek pehle jaao —\n"
                         f"/checkin bhejo jab ho jaao.\n\n"
                         f"Partner ko instant notification milega.\n"
                         f"Unhe wait mat karao. 🔥",
                    parse_mode="Markdown"
                )

                await context.bot.send_message(
                    chat_id=partner_id,
                    text=f"🤝 *Partner Match Confirmed!*\n\n"
                         f"*{partner_name}* ↔ *{user.first_name}*\n"
                         f"📚 Exam: {exam}\n"
                         f"⏰ Study Time: {study_time}\n\n"
                         f"Tumhara pehla check-in aaj hai.\n"
                         f"Koi ek pehle jaao —\n"
                         f"/checkin bhejo jab ho jaao.\n\n"
                         f"Partner ko instant notification milega.\n"
                         f"Unhe wait mat karao. 🔥",
                    parse_mode="Markdown"
                )

                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"🎯 *NEW RANDOM MATCH!*\n\n"
                         f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                         f"👤 *Student 1:*\n"
                         f"   Name: {user.first_name}\n"
                         f"   Username: {user_display}\n"
                         f"   ID: `{user.id}`\n\n"
                         f"👤 *Student 2:*\n"
                         f"   Name: {partner_name}\n"
                         f"   Username: {partner_display}\n"
                         f"   ID: `{partner_id}`\n\n"
                         f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                         f"📚 *Exam:* {exam}\n"
                         f"⏰ *Study Time:* {study_time}\n"
                         f"🔗 *Pair Type:* Random\n\n"
                         f"✅ *Steps:*\n"
                         f"1️⃣ Create private group\n"
                         f"2️⃣ Add {user_display}\n"
                         f"3️⃣ Add {partner_display}\n"
                         f"4️⃣ Add bot as admin\n"
                         f"5️⃣ /send_invite {user.id} {partner_id}",
                    parse_mode="Markdown"
                )

            else:
                c.execute("""SELECT COUNT(*) FROM waiting_queue
                             WHERE exam=? AND study_time=?""",
                          (exam, study_time))
                position = c.fetchone()[0]

                c.execute("""INSERT OR REPLACE INTO waiting_queue
                    (user_id, exam, study_time, language, joined_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (user.id, exam, study_time, language,
                     datetime.now(INDIA_TZ).isoformat()))
                c.execute("""DELETE FROM temp_registration
                             WHERE user_id=?""", (user.id,))
                conn.commit()
                conn.close()

                await query.edit_message_text(
                    f"✅ *Registration complete!*\n\n"
                    f"📚 *Exam:* {exam}\n"
                    f"⏰ *Study Time:* {study_time}\n"
                    f"🗣 *Language:* {language}\n\n"
                    f"⏳ *Looking for your study partner...*\n"
                    f"📊 Queue position: #{position + 1}\n\n"
                    f"You will be notified when matched!\n"
                    f"📖 Use /rules to learn how this works.",
                    parse_mode="Markdown"
                )

# ================= CHECKIN =================
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_date = today()

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT streak, last_checkin, partner_id,
                 group_id, reputation FROM users WHERE user_id=?""",
              (user_id,))
    row = c.fetchone()

    if not row:
        await update.message.reply_text(
            "❌ *Not registered!* Use /start first.",
            parse_mode="Markdown")
        conn.close()
        return

    streak, last_checkin, partner_id, group_id, reputation = row
    last = parse_date(last_checkin)

    if last == today_date:
        await update.message.reply_text(
            "✅ *Already checked in today!* Come back tomorrow. 💪",
            parse_mode="Markdown")
        conn.close()
        return

    if last == today_date - timedelta(days=1):
        streak += 1
        reputation += 2
        message = f"🔥 *Streak:* {streak} days\n⭐ *Reputation:* +2 points"
    else:
        streak = 1
        reputation -= 5
        message = f"🔄 *Streak reset!* New streak: 1\n⚠️ *Reputation:* -5"

    reputation = max(0, min(100, reputation))

    c.execute("""UPDATE users SET streak=?, last_checkin=?, reputation=?
                 WHERE user_id=?""",
              (streak, today_date.strftime("%Y-%m-%d"),
               reputation, user_id))
    conn.commit()

    # Milestone messages
    milestone_msg = ""
    if streak == 7:
        milestone_msg = "\n\n🎉 *7-day streak! One week strong!*"
        # Send invite after 7 day streak
        await context.bot.send_message(
            chat_id=user_id,
            text="🔥 *7 din ho gaye!*\n\n"
                 "Ab apne dost ko bulao!\n\n"
                 "Use /invite to get your personal link! 🔗",
            parse_mode="Markdown"
        )
    elif streak == 30:
        milestone_msg = "\n\n🏆 *30-day streak! Incredible!*"
    elif streak == 100:
        milestone_msg = "\n\n💎 *100-day streak! LEGENDARY!*"

    conn.close()

    await update.message.reply_text(
        f"✅ *Check-in recorded!*\n\n{message}\n\n"
        f"📊 *Total Reputation:* {reputation}/100"
        f"{milestone_msg}",
        parse_mode="Markdown"
    )

    if partner_id:
        await context.bot.send_message(
            chat_id=partner_id,
            text=f"👀 *{update.effective_user.first_name} "
                 f"just checked in!*\n\n"
                 f"Don't fall behind — use /checkin now! 💪",
            parse_mode="Markdown"
        )

    if group_id:
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=f"✅ *{update.effective_user.first_name}* "
                     f"checked in!\n"
                     f"🔥 Streak: *{streak}* days",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Group notification failed: {e}")

    # Check streak competition for invited pairs
    if partner_id and streak >= 3:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""SELECT pg.pair_type, u.streak,
                     u.streak_competition_sent
                     FROM pending_groups pg
                     JOIN users u ON u.user_id=?
                     WHERE (pg.user1_id=? AND pg.user2_id=?)
                     OR (pg.user1_id=? AND pg.user2_id=?)""",
                  (partner_id, user_id, partner_id,
                   partner_id, user_id))
        comp_row = c.fetchone()

        if comp_row:
            pair_type, partner_streak, comp_sent = comp_row
            c.execute("""SELECT streak_competition_sent
                         FROM users WHERE user_id=?""", (user_id,))
            my_sent = c.fetchone()
            my_sent = my_sent[0] if my_sent else 0

            if (pair_type == "invited" and
                    partner_streak >= 3 and
                    not comp_sent and not my_sent):

                c.execute("""SELECT first_name FROM users
                             WHERE user_id=?""", (partner_id,))
                partner_name_row = c.fetchone()
                partner_name = partner_name_row[0] \
                    if partner_name_row else "Partner"

                c.execute("""SELECT first_name FROM users
                             WHERE user_id=?""", (user_id,))
                my_name_row = c.fetchone()
                my_name = my_name_row[0] if my_name_row else "You"

                # Message to current user (inviter)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🏆 *{partner_name} ne 3 check-ins "
                         f"complete kiye!* 💪\n\n"
                         f"Tumhara invite kaam aaya.\n\n"
                         f"*Streak Race:*\n"
                         f"Tumhara: {streak} days\n"
                         f"Unka: {partner_streak} days\n\n"
                         f"Kaun 7 tak pahunchta hai pehle? 😏",
                    parse_mode="Markdown"
                )

                # Message to partner (invited)
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=f"🏆 *{my_name} ne tumhe invite kiya tha.*\n\n"
                         f"3 days ho gaye — solid start! 🔥\n\n"
                         f"*Streak Race:*\n"
                         f"Tumhara: {partner_streak} days\n"
                         f"Unka: {streak} days\n\n"
                         f"Unse aage nikal sakte ho? 😏",
                    parse_mode="Markdown"
                )

                c.execute("""UPDATE users SET
                             streak_competition_sent=1
                             WHERE user_id IN (?, ?)""",
                          (user_id, partner_id))
                conn.commit()
        conn.close()

    # Send invite after first checkin
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT invite_link_generated FROM users
                 WHERE user_id=?""", (user_id,))
    inv_row = c.fetchone()
    conn.close()

    if inv_row and inv_row[0] == 0 and streak == 1:
        user_obj = update.effective_user
        if user_obj.username:
            invite_link = (f"https://t.me/{BOT_USERNAME}"
                           f"?start=REF_{user_obj.username}")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 *Pehla check-in ho gaya!*\n\n"
                     f"Ab apne dost ko invite karo:\n\n"
                     f"`{invite_link}`\n\n"
                     f"Woh join karte hi directly "
                     f"tumse pair ho jaenge! 🎯",
                parse_mode="Markdown"
            )
            conn = get_conn()
            c = conn.cursor()
            c.execute("""UPDATE users SET invite_link_generated=1
                         WHERE user_id=?""", (user_id,))
            conn.commit()
            conn.close()

# ================= STREAK =================
async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT first_name, streak, reputation, exam
                 FROM users WHERE user_id=?""", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(
            "❌ *Not registered!* Use /start first.",
            parse_mode="Markdown")
        return

    name, streak, reputation, exam = row
    tier = get_tier(reputation)

    await update.message.reply_text(
        f"📊 *{name}'s Stats*\n\n"
        f"📚 *Exam:* {exam}\n"
        f"🔥 *Streak:* {streak} days\n"
        f"⭐ *Reputation:* {reputation}/100\n"
        f"🏆 *Tier:* {tier}\n\n"
        f"💪 Keep studying every day!",
        parse_mode="Markdown"
    )

# ================= PARTNER =================
async def partner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row or not row[0]:
        await update.message.reply_text(
            "⏳ *No partner yet!* Waiting for match...",
            parse_mode="Markdown")
        conn.close()
        return

    partner_id = row[0]
    c.execute("""SELECT first_name, username, exam,
                 streak, reputation, study_time, language
                 FROM users WHERE user_id=?""", (partner_id,))
    p = c.fetchone()
    conn.close()

    if p:
        username_display = f"@{p[1]}" if p[1] else "No username"
        tier = get_tier(p[4])
        await update.message.reply_text(
            f"👥 *Your Study Partner*\n\n"
            f"👤 *Name:* {p[0]}\n"
            f"📱 *Username:* {username_display}\n"
            f"📚 *Exam:* {p[2]}\n"
            f"⏰ *Study Time:* {p[5]}\n"
            f"🗣 *Language:* {p[6]}\n"
            f"🔥 *Streak:* {p[3]} days\n"
            f"⭐ *Reputation:* {p[4]}/100\n"
            f"🏆 *Tier:* {tier}\n\n"
            f"💬 Motivate each other!",
            parse_mode="Markdown"
        )

# ================= RULES =================
async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *PrepRoom Accountability Rules*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ *Daily Check-in*\n"
        "• Use /checkin every day\n"
        "• Partner notified when you check in\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔥 *Streaks*\n"
        "• +1 streak each consecutive day\n"
        "• Miss a day = streak resets\n"
        "• Milestones: 7, 30, 100 days 🎉\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⭐ *Reputation*\n"
        "• Start at 40 points\n"
        "• +2 per check-in | -5 per missed day\n"
        "• 🥉Bronze → 🥈Silver → 🥇Gold → 💎Diamond\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👻 *Ghost Rules*\n"
        "• Day 1 missed = Reminder\n"
        "• Day 2 missed = Warning\n"
        "• Day 3 missed = -15 rep + reassigned\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 *Referral*\n"
        "• Use /invite to get your personal link\n"
        "• Friends join directly as your partner\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 *All Commands:* /help\n\n"
        "💪 *Consistency beats perfection!*",
        parse_mode="Markdown"
    )

# ================= REPORT =================
async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT partner_id, first_name
                 FROM users WHERE user_id=?""", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row or not row[0]:
        await update.message.reply_text(
            "❌ *No partner to report!*",
            parse_mode="Markdown")
        return

    partner_id, partner_name = row

    await update.message.reply_text(
        "⚠️ *Report submitted!*\n\n"
        "Admin will review within 24 hours. 💪",
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"🚨 *INACTIVITY REPORT*\n\n"
             f"📢 *By:* `{user_id}`\n"
             f"👤 *Reported:* {partner_name} (`{partner_id}`)",
        parse_mode="Markdown"
    )

# ================= MORNING REMINDER =================
async def morning_reminder(context):
    logger.info("Running morning reminder...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, first_name FROM users WHERE banned=0")
    users = c.fetchall()
    conn.close()

    for user_id, first_name in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🌅 *Good Morning {first_name}!*\n\n"
                     f"A new day = a new chance! 💪\n\n"
                     f"📚 Study hard and use /checkin after!\n\n"
                     f"Your partner is counting on you! 🔥",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Morning reminder failed for {user_id}: {e}")

# ================= WEEKLY REPORT =================
async def weekly_report(context):
    logger.info("Running weekly report...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT user_id, first_name, streak,
                 reputation FROM users WHERE banned=0""")
    users = c.fetchall()
    conn.close()

    for user_id, first_name, streak, reputation in users:
        tier = get_tier(reputation)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📊 *Weekly Report — {first_name}*\n\n"
                     f"🔥 *Streak:* {streak} days\n"
                     f"⭐ *Reputation:* {reputation}/100\n"
                     f"🏆 *Tier:* {tier}\n\n"
                     f"💪 Keep going this week!\n"
                     f"Use /leaderboard to see your rank!\n"
                     f"Use /brag to share your stats!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Weekly report failed for {user_id}: {e}")

# ================= DAILY CHECK =================
async def daily_check(context):
    logger.info("Running daily check...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT user_id, first_name, last_checkin,
                 partner_id, reputation, streak
                 FROM users WHERE banned=0""")
    users = c.fetchall()

    for user_id, first_name, last_checkin, \
            partner_id, reputation, streak in users:
        missed = days_missed(last_checkin)

        if missed == 1:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ *Hey {first_name}!*\n\n"
                         f"You haven't checked in today!\n\n"
                         f"Don't break your *{streak} day streak!*\n\n"
                         f"Use /checkin now! 💪",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Day 1 reminder failed: {e}")

        elif missed == 2:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ *{first_name}, 2 days missed!*\n\n"
                         f"Use /checkin now!\n\n"
                         f"One more day missed:\n"
                         f"• -15 reputation\n"
                         f"• Partner reassignment\n\n"
                         f"Your partner is waiting! 🙏",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Day 2 warning failed: {e}")

        elif missed >= 3:
            new_rep = max(0, reputation - 15)
            c.execute("""UPDATE users SET reputation=?, partner_id=NULL
                         WHERE user_id=?""", (new_rep, user_id))

            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"👻 *{first_name}, marked inactive!*\n\n"
                         f"• Reputation: -15\n"
                         f"• Partner reassigned\n\n"
                         f"Use /start for new partner! 💪",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Ghost msg failed: {e}")

            if partner_id:
                c.execute("""UPDATE users SET partner_id=NULL
                             WHERE user_id=?""", (partner_id,))
                try:
                    await context.bot.send_message(
                        chat_id=partner_id,
                        text="😔 *Partner inactive 3+ days.*\n\n"
                             "Use /start to rematch! 💪",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Partner msg failed: {e}")

                c.execute("""SELECT wq.user_id FROM waiting_queue wq
                             WHERE wq.exam=(
                                 SELECT exam FROM users WHERE user_id=?)
                             AND wq.study_time=(
                                 SELECT study_time FROM users
                                 WHERE user_id=?)
                             LIMIT 1""", (partner_id, partner_id))
                new_match = c.fetchone()

                if new_match:
                    new_partner_id = new_match[0]
                    now = datetime.now(INDIA_TZ).isoformat()
                    c.execute("""UPDATE users SET partner_id=?,
                                 matched_at=? WHERE user_id=?""",
                              (new_partner_id, now, partner_id))
                    c.execute("""UPDATE users SET partner_id=?,
                                 matched_at=? WHERE user_id=?""",
                              (partner_id, now, new_partner_id))
                    c.execute("""DELETE FROM waiting_queue
                                 WHERE user_id=?""", (new_partner_id,))
                    try:
                        await context.bot.send_message(
                            chat_id=partner_id,
                            text="🎉 *New partner found!*\n\n"
                                 "Use /partner to see details! 💪",
                            parse_mode="Markdown"
                        )
                        await context.bot.send_message(
                            chat_id=new_partner_id,
                            text="🎉 *New study partner!*\n\n"
                                 "Use /partner to see details! 💪",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Rematch msg failed: {e}")

            try:
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"👻 *GHOST!*\n\n"
                         f"👤 {first_name} (`{user_id}`)\n"
                         f"📉 -15 reputation\n"
                         f"🔄 Partner reassigned",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Admin ghost msg failed: {e}")

    conn.commit()
    conn.close()

# ================= ADMIN: ALL DATA =================
async def alldata_cmd(update: Update,
                      context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()

    # Summary stats
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE partner_id IS NOT NULL")
    matched = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM waiting_queue")
    waiting = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM users WHERE last_checkin=?""",
              (today().strftime("%Y-%m-%d"),))
    checked_today = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals")
    total_referrals = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals WHERE pair_formed=1")
    successful_referrals = c.fetchone()[0]

    summary = (
        f"📊 *PrepRoom Complete Data*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Total Users:* {total}\n"
        f"🤝 *Matched:* {matched}\n"
        f"⏳ *Waiting:* {waiting}\n"
        f"✅ *Checked Today:* {checked_today}\n"
        f"🚫 *Banned:* {banned}\n\n"
        f"🔗 *Total Referrals:* {total_referrals}\n"
        f"✅ *Successful Referrals:* {successful_referrals}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await update.message.reply_text(summary, parse_mode="Markdown")

    # All users list
    c.execute("""SELECT user_id, first_name, username,
                 exam, streak, reputation, last_checkin,
                 partner_id, referred_by
                 FROM users ORDER BY streak DESC""")
    all_users = c.fetchall()
    conn.close()

    if not all_users:
        await update.message.reply_text(
            "No users yet!", parse_mode="Markdown")
        return

    # Send in chunks of 10
    chunk_size = 10
    for i in range(0, len(all_users), chunk_size):
        chunk = all_users[i:i + chunk_size]
        msg = f"👥 *Users {i+1} to {i+len(chunk)}:*\n\n"

        for u in chunk:
            uid, name, uname, exam, streak, rep, \
                last_ci, pid, ref_by = u
            tier = get_tier(rep)
            partner = f"`{pid}`" if pid else "None"
            ref = f"@{ref_by}" if ref_by else "Direct"
            msg += (
                f"👤 *{name}*\n"
                f"   ID: `{uid}`\n"
                f"   @{uname or 'no username'}\n"
                f"   📚 {exam}\n"
                f"   🔥 {streak} days | {tier}\n"
                f"   📅 Last: {last_ci or 'Never'}\n"
                f"   👥 Partner: {partner}\n"
                f"   🔗 Ref: {ref}\n\n"
            )

        await update.message.reply_text(msg, parse_mode="Markdown")

# ================= ADMIN: SEND INVITE =================
async def send_invite_cmd(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ *Usage:* /send_invite [user1_id] [user2_id]",
            parse_mode="Markdown")
        return

    try:
        u1 = int(context.args[0])
        u2 = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ *Invalid IDs!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT match_id FROM pending_groups
                 WHERE ((user1_id=? AND user2_id=?)
                 OR (user1_id=? AND user2_id=?))
                 AND status='pending' LIMIT 1""",
              (u1, u2, u2, u1))
    match = c.fetchone()
    conn.close()

    if not match:
        await update.message.reply_text(
            "❌ *No pending match for these users!*",
            parse_mode="Markdown")
        return

    match_id = match[0]
    chat_id = update.effective_chat.id

    if chat_id == ADMIN_USER_ID:
        await update.message.reply_text(
            "⚠️ *Use this command INSIDE the group you created!*\n\n"
            "1. Create group\n"
            "2. Add both students\n"
            "3. Add bot as admin\n"
            "4. Type /send_invite [id1] [id2] inside group",
            parse_mode="Markdown"
        )
        return

    try:
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=chat_id,
            member_limit=2,
            name=f"PrepRoom Match #{match_id}"
        )

        link = invite_link.invite_link

        conn = get_conn()
        c = conn.cursor()
        c.execute("""UPDATE users SET group_id=?
                     WHERE user_id IN (?, ?)""", (chat_id, u1, u2))
        c.execute("""UPDATE pending_groups SET status='done'
                     WHERE match_id=?""", (match_id,))
        conn.commit()
        conn.close()

        await context.bot.send_message(
            chat_id=u1,
            text=f"🎉 *Your study group is ready!*\n\n"
                 f"👉 {link}\n\n"
                 f"This link is only for you! 🔒",
            parse_mode="Markdown"
        )

        await context.bot.send_message(
            chat_id=u2,
            text=f"🎉 *Your study group is ready!*\n\n"
                 f"👉 {link}\n\n"
                 f"This link is only for you! 🔒",
            parse_mode="Markdown"
        )

        await update.message.reply_text(
            "✅ *Invite links sent to both students!*",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Send invite failed: {e}")
        await update.message.reply_text(
            f"❌ *Error:* {str(e)}\n\n"
            f"Make sure bot is admin in the group!",
            parse_mode="Markdown"
        )

# ================= ADMIN: GROUP READY =================
async def group_ready(update: Update,
                      context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT match_id, user1_id, user2_id
                 FROM pending_groups
                 WHERE status='pending' LIMIT 1""")
    match = c.fetchone()

    if not match:
        await update.message.reply_text(
            "ℹ️ *No pending matches.*",
            parse_mode="Markdown")
        conn.close()
        return

    match_id, u1, u2 = match
    group_id = update.effective_chat.id

    c.execute("""UPDATE users SET group_id=?
                 WHERE user_id IN (?, ?)""", (group_id, u1, u2))
    c.execute("""UPDATE pending_groups SET status='done'
                 WHERE match_id=?""", (match_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ *Group linked!*",
        parse_mode="Markdown"
    )

# ================= ADMIN: PENDING =================
async def pending_cmd(update: Update,
                      context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT pg.match_id, pg.user1_id, pg.user2_id,
                 pg.matched_at, pg.pair_type,
                 u1.first_name, u2.first_name
                 FROM pending_groups pg
                 LEFT JOIN users u1 ON pg.user1_id = u1.user_id
                 LEFT JOIN users u2 ON pg.user2_id = u2.user_id
                 WHERE pg.status='pending'""")
    matches = c.fetchall()
    conn.close()

    if not matches:
        await update.message.reply_text(
            "✅ *No pending matches!*",
            parse_mode="Markdown")
        return

    msg = "📋 *Pending Matches:*\n\n"
    for m in matches:
        msg += f"🔹 *Match #{m[0]}* ({m[4]})\n"
        msg += f"   👤 {m[5]} (`{m[1]}`)\n"
        msg += f"   👤 {m[6]} (`{m[2]}`)\n"
        msg += f"   🕐 {m[3][:16]}\n"
        msg += f"   👉 /send_invite {m[1]} {m[2]}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= ADMIN: USERS =================
async def users_cmd(update: Update,
                    context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM waiting_queue")
    waiting = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE partner_id IS NOT NULL")
    matched = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM users WHERE last_checkin=?""",
              (today().strftime("%Y-%m-%d"),))
    checked_today = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals WHERE pair_formed=1")
    ref_success = c.fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"📊 *PrepRoom Stats*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Total Users:* {total}\n"
        f"🤝 *Matched:* {matched}\n"
        f"⏳ *Waiting:* {waiting}\n"
        f"✅ *Checked Today:* {checked_today}\n"
        f"🚫 *Banned:* {banned}\n"
        f"🔗 *Successful Referrals:* {ref_success}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Use /alldata for full user list",
        parse_mode="Markdown"
    )

# ================= ADMIN: FIND =================
async def find_cmd(update: Update,
                   context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ *Usage:* /find [user_id]",
            parse_mode="Markdown")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ *Invalid ID!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT first_name, username, exam, study_time,
                 language, streak, reputation, last_checkin,
                 partner_id, banned, warnings, referred_by
                 FROM users WHERE user_id=?""", (target_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("❌ *User not found!*",
                                        parse_mode="Markdown")
        return

    name, username, exam, study_time, language, streak, \
        reputation, last_checkin, partner_id, \
        banned, warnings, referred_by = row

    username_display = f"@{username}" if username else "Not set"
    tier = get_tier(reputation)
    status = "🚫 Banned" if banned else "✅ Active"
    ref_by = f"@{referred_by}" if referred_by else "Direct"

    await update.message.reply_text(
        f"🔍 *User Found*\n\n"
        f"👤 *Name:* {name}\n"
        f"📱 *Username:* {username_display}\n"
        f"🆔 *ID:* `{target_id}`\n\n"
        f"📚 *Exam:* {exam}\n"
        f"⏰ *Study Time:* {study_time}\n"
        f"🗣 *Language:* {language}\n\n"
        f"🔥 *Streak:* {streak} days\n"
        f"⭐ *Reputation:* {reputation}/100\n"
        f"🏆 *Tier:* {tier}\n"
        f"📅 *Last Check-in:* {last_checkin}\n\n"
        f"👥 *Partner ID:* {partner_id}\n"
        f"🔗 *Referred by:* {ref_by}\n"
        f"⚠️ *Warnings:* {warnings}\n"
        f"🔰 *Status:* {status}",
        parse_mode="Markdown"
    )

# ================= ADMIN: REMATCH =================
async def rematch_cmd(update: Update,
                      context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ *Usage:* /rematch [user_id]",
            parse_mode="Markdown")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ *Invalid ID!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT exam, study_time FROM users
                 WHERE user_id=?""", (target_id,))
    row = c.fetchone()

    if not row:
        await update.message.reply_text("❌ *User not found!*",
                                        parse_mode="Markdown")
        conn.close()
        return

    exam, study_time = row
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?",
              (target_id,))

    c.execute("""SELECT user_id FROM waiting_queue
                 WHERE exam=? AND study_time=? AND user_id!=?
                 LIMIT 1""", (exam, study_time, target_id))
    match = c.fetchone()

    if match:
        new_partner_id = match[0]
        now = datetime.now(INDIA_TZ).isoformat()
        c.execute("""UPDATE users SET partner_id=?, matched_at=?
                     WHERE user_id=?""",
                  (new_partner_id, now, target_id))
        c.execute("""UPDATE users SET partner_id=?, matched_at=?
                     WHERE user_id=?""",
                  (target_id, now, new_partner_id))
        c.execute("DELETE FROM waiting_queue WHERE user_id=?",
                  (new_partner_id,))
        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"✅ *Rematched!*\n\nNew partner: `{new_partner_id}`",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🎉 *Admin found you a new partner!*\n\n"
                     "Use /partner to see details! 💪",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=new_partner_id,
                text="🎉 *New study partner!*\n\n"
                     "Use /partner to see details! 💪",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Rematch notification failed: {e}")
    else:
        c.execute("""INSERT OR REPLACE INTO waiting_queue
                     (user_id, exam, study_time, joined_at)
                     VALUES (?, ?, ?, ?)""",
                  (target_id, exam, study_time,
                   datetime.now(INDIA_TZ).isoformat()))
        conn.commit()
        conn.close()

        await update.message.reply_text(
            "⏳ *No match found. Added to waiting queue.*",
            parse_mode="Markdown"
        )

# ================= ADMIN: BAN =================
async def ban_cmd(update: Update,
                  context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ *Usage:* /ban [user_id]",
            parse_mode="Markdown")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ *Invalid ID!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET banned=1 WHERE user_id=?",
              (target_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🚫 *User `{target_id}` banned.*",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="🚫 *You have been banned from PrepRoom.*",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ban notification failed: {e}")

# ================= ADMIN: UNBAN =================
async def unban_cmd(update: Update,
                    context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ *Usage:* /unban [user_id]",
            parse_mode="Markdown")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ *Invalid ID!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET banned=0 WHERE user_id=?",
              (target_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ *User `{target_id}` unbanned.*",
        parse_mode="Markdown"
    )

# ================= ADMIN: BROADCAST =================
async def broadcast_cmd(update: Update,
                        context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ *Usage:* /broadcast [message]",
            parse_mode="Markdown")
        return

    message = " ".join(context.args)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE banned=0")
    users = c.fetchall()
    conn.close()

    sent = 0
    failed = 0

    for (user_id,) in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Message from PrepRoom:*\n\n{message}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception as e:
            failed += 1

    await update.message.reply_text(
        f"✅ *Broadcast done!*\n\n"
        f"📤 Sent: {sent}\n❌ Failed: {failed}",
        parse_mode="Markdown"
    )

# ================= ADMIN: EXPORT DATA =================
async def exportdata_cmd(update: Update,
                         context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    await update.message.reply_text(
        "⏳ *Preparing export...*",
        parse_mode="Markdown"
    )

    conn = get_conn()
    c = conn.cursor()

    # Get all users
    c.execute("""SELECT user_id, first_name, username, exam,
                 study_time, language, streak, reputation,
                 last_checkin, partner_id, matched_at,
                 banned, referred_by
                 FROM users ORDER BY streak DESC""")
    users = c.fetchall()
    conn.close()

    if not users:
        await update.message.reply_text(
            "❌ *No data to export!*",
            parse_mode="Markdown")
        return

    # Build CSV content
    csv_lines = []
    csv_lines.append(
        "user_id,first_name,username,exam,study_time,"
        "language,streak,reputation,last_checkin,"
        "partner_id,matched_at,banned,referred_by"
    )

    for u in users:
        row = []
        for field in u:
            if field is None:
                row.append("")
            else:
                # Clean commas from text fields
                row.append(str(field).replace(",", ";"))
        csv_lines.append(",".join(row))

    csv_content = "\n".join(csv_lines)

    # Save to temp file
    filename = f"preproom_export_{today().strftime('%Y%m%d')}.csv"
    filepath = f"/data/{filename}"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(csv_content)

        # Send file to admin
        with open(filepath, "rb") as f:
            await context.bot.send_document(
                chat_id=ADMIN_USER_ID,
                document=f,
                filename=filename,
                caption=f"📊 *PrepRoom Data Export*\n\n"
                        f"📅 Date: {today().strftime('%d %b %Y')}\n"
                        f"👥 Total Users: {len(users)}\n\n"
                        f"Open in Google Sheets or Excel!",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Export failed: {e}")

        # Fallback — send as text if file fails
        await update.message.reply_text(
            "⚠️ *File export failed. Sending as text...*",
            parse_mode="Markdown"
        )

        # Send first 20 rows as text
        msg = "📊 *Export (first 20 users):*\n\n"
        for u in users[:20]:
            msg += (
                f"👤 {u[1]} | @{u[2] or 'none'}\n"
                f"   📚 {u[3]} | 🔥 {u[6]} days\n"
                f"   ⭐ {u[7]}/100 | 📅 {u[8] or 'Never'}\n\n"
            )
        await update.message.reply_text(
            msg, parse_mode="Markdown")

# ================= ADMIN: CHECK DB =================
async def checkdb_cmd(update: Update,
                      context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()

    # Count rows in each table
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM waiting_queue")
    total_queue = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM pending_groups")
    total_groups = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM pending_groups WHERE status='pending'")
    pending_groups = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM referrals")
    total_referrals = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM feedback")
    total_feedback = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM blocked_pairs")
    total_blocked = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM temp_registration")
    total_temp = c.fetchone()[0]

    # Last registration
    c.execute("""SELECT first_name, matched_at FROM users
                 WHERE matched_at IS NOT NULL
                 ORDER BY matched_at DESC LIMIT 1""")
    last_match = c.fetchone()

    # Last checkin
    c.execute("""SELECT first_name, last_checkin FROM users
                 WHERE last_checkin IS NOT NULL
                 ORDER BY last_checkin DESC LIMIT 1""")
    last_ci = c.fetchone()

    # Broken records — users with partner_id but partner doesnt exist
    c.execute("""SELECT COUNT(*) FROM users u
                 WHERE u.partner_id IS NOT NULL
                 AND NOT EXISTS (
                     SELECT 1 FROM users u2
                     WHERE u2.user_id = u.partner_id
                 )""")
    broken_partners = c.fetchone()[0]

    # Users with no exam set
    c.execute("""SELECT COUNT(*) FROM users
                 WHERE exam IS NULL OR exam = ''""")
    no_exam = c.fetchone()[0]

    conn.close()

    # Check DB file size
    try:
        import os as _os
        db_size = _os.path.getsize(DB_NAME)
        if db_size < 1024:
            size_str = f"{db_size} bytes"
        elif db_size < 1024 * 1024:
            size_str = f"{db_size // 1024} KB"
        else:
            size_str = f"{db_size // (1024 * 1024)} MB"
    except Exception:
        size_str = "Unknown"

    # Health status
    health = "✅ Healthy"
    issues = []

    if broken_partners > 0:
        issues.append(f"⚠️ {broken_partners} broken partner links")
    if no_exam > 0:
        issues.append(f"⚠️ {no_exam} users with no exam set")
    if total_temp > 5:
        issues.append(f"⚠️ {total_temp} stuck temp registrations")

    if issues:
        health = "⚠️ Issues Found"

    last_match_str = (f"{last_match[0]} at {last_match[1][:16]}"
                      if last_match else "None")
    last_ci_str = (f"{last_ci[0]} on {last_ci[1]}"
                   if last_ci else "None")

    msg = (
        f"🔍 *Database Health Check*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💾 *DB Size:* {size_str}\n"
        f"🏥 *Status:* {health}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Table Counts:*\n"
        f"👥 Users: {total_users}\n"
        f"⏳ Waiting Queue: {total_queue}\n"
        f"🤝 Pending Groups: {pending_groups}\n"
        f"📋 Total Groups: {total_groups}\n"
        f"🔗 Referrals: {total_referrals}\n"
        f"💬 Feedback: {total_feedback}\n"
        f"🚫 Blocked Pairs: {total_blocked}\n"
        f"⏱ Temp Registrations: {total_temp}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🕐 *Last Match:* {last_match_str}\n"
        f"✅ *Last Check-in:* {last_ci_str}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if issues:
        msg += "*⚠️ Issues:*\n"
        for issue in issues:
            msg += f"{issue}\n"
    else:
        msg += "✅ *No issues found!*"

    await update.message.reply_text(msg, parse_mode="Markdown")
                        
# ================= ADMIN: REFERRAL STATS =================
async def referral_stats_cmd(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT r.inviter_username, COUNT(*) as total,
                 SUM(r.pair_formed) as successful
                 FROM referrals r
                 GROUP BY r.inviter_id
                 ORDER BY total DESC LIMIT 10""")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "📊 *No referral data yet.*",
            parse_mode="Markdown")
        return

    msg = "🔗 *Top Referrers:*\n\n"
    for i, (username, total, successful) in enumerate(rows, 1):
        msg += (f"{i}. @{username or 'unknown'}\n"
                f"   Invited: {total} | "
                f"Converted: {successful or 0}\n\n")

    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= MAIN =================
def main():
    print("=" * 50)
    print("🚀 PREPROOM ACCOUNTABILITY BOT")
    print("=" * 50)

    if not TOKEN:
        print("❌ ERROR: TOKEN not set!")
        return

    if ADMIN_USER_ID == 0:
        print("❌ ERROR: ADMIN_USER_ID not set!")
        return

    print(f"✅ Token loaded")
    print(f"✅ Admin ID: {ADMIN_USER_ID}")
    print(f"✅ Bot Username: @{BOT_USERNAME}")
    print(f"✅ DB Path: {DB_NAME}")
    print("=" * 50)

    setup_db()

    app = Application.builder().token(TOKEN).build()

    job_queue = app.job_queue

    job_queue.run_daily(
        morning_reminder,
        time=dtime(hour=8, minute=0, second=0, tzinfo=INDIA_TZ)
    )
    job_queue.run_daily(
        daily_check,
        time=dtime(hour=12, minute=0, second=0, tzinfo=INDIA_TZ)
    )
    job_queue.run_daily(
        weekly_report,
        time=dtime(hour=9, minute=0, second=0, tzinfo=INDIA_TZ),
        days=(6,)
    )

    # Student commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("partner", partner_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("leave", leave_cmd))
    app.add_handler(CommandHandler("block", block_cmd))
    app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(CommandHandler("feedback", feedback_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("invite", invite_cmd))
    app.add_handler(CommandHandler("brag", brag_cmd))

    # Admin commands
    app.add_handler(CommandHandler("group_ready", group_ready))
    app.add_handler(CommandHandler("send_invite", send_invite_cmd))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("alldata", alldata_cmd))
    app.add_handler(CommandHandler("find", find_cmd))
    app.add_handler(CommandHandler("rematch", rematch_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("refstats", referral_stats_cmd))
    app.add_handler(CommandHandler("exportdata", exportdata_cmd))
    app.add_handler(CommandHandler("checkdb", checkdb_cmd))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_feedback))

    print("🎯 Bot is running!")
    print("=" * 50)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
