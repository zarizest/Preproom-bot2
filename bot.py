import os
import sqlite3
import logging
from datetime import datetime, timedelta, time as dtime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ================= CONFIGURATION =================
TOKEN = os.getenv("TOKEN","8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "8456901459"))

DB_NAME = "preproom.db"
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
        warnings INTEGER DEFAULT 0
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
        status TEXT DEFAULT 'pending'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS temp_registration (
        user_id INTEGER PRIMARY KEY,
        exam TEXT,
        study_time TEXT
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
            "🚫 *You have been banned from PrepRoom.*\n\n"
            "Contact admin if you think this is a mistake.",
            parse_mode="Markdown"
        )
        return

    keyboard = [
        [InlineKeyboardButton("🏢 Campus Placements", callback_data="cat_campus")],
        [InlineKeyboardButton("📋 Government Exams", callback_data="cat_govt")],
        [InlineKeyboardButton("🏥 Medical Entrance", callback_data="cat_medical")],
        [InlineKeyboardButton("🔬 Engineering Entrance", callback_data="cat_engineering")],
        [InlineKeyboardButton("🎓 MBA / GATE", callback_data="cat_mba")],
        [InlineKeyboardButton("📚 Semester / Other", callback_data="cat_semester")],
    ]

    await update.message.reply_text(
        "👋 *Welcome to PrepRoom!*\n\n"
        "I'll match you with a study partner.\n\n"
        "📚 *Select your exam category:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
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
                 partner_id, matched_at
                 FROM users WHERE user_id=?""", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(
            "❌ *Not registered!* Use /start first.",
            parse_mode="Markdown")
        return

    name, username, exam, study_time, language, streak, \
        reputation, last_checkin, partner_id, matched_at = row

    username_display = f"@{username}" if username else "Not set"
    tier = get_tier(reputation)
    partner_status = "✅ Matched" if partner_id else "⏳ Waiting"
    last = last_checkin if last_checkin else "Never"

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
        f"👥 *Partner Status:* {partner_status}",
        parse_mode="Markdown"
    )

# ================= EDIT =================
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 Change Exam", callback_data="edit_exam")],
        [InlineKeyboardButton("⏰ Change Study Time", callback_data="edit_time")],
        [InlineKeyboardButton("🗣 Change Language", callback_data="edit_lang")],
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
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (user_id,))
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (partner_id,))
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
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (user_id,))
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (partner_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "🚫 *Partner blocked successfully.*\n\n"
        "They will not be matched with you again.\n\n"
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
        "Type your message and send it.\n"
        "Admin will review it shortly! 😊",
        parse_mode="Markdown"
    )

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        "✅ *Feedback sent! Thank you!* 🙏\n\n"
        "Admin will review your feedback shortly.",
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
async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT first_name, streak, reputation
                 FROM users ORDER BY streak DESC LIMIT 10""")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "⏳ *No data yet!* Be the first to check in!",
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
    msg += "💪 *Keep studying to climb the ranks!*"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= BUTTON HANDLER =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    # Edit options
    if data == "edit_exam":
        keyboard = [
            [InlineKeyboardButton("🏢 Campus Placements",
                                  callback_data="cat_campus")],
            [InlineKeyboardButton("📋 Government Exams",
                                  callback_data="cat_govt")],
            [InlineKeyboardButton("🏥 Medical Entrance",
                                  callback_data="cat_medical")],
            [InlineKeyboardButton("🔬 Engineering Entrance",
                                  callback_data="cat_engineering")],
            [InlineKeyboardButton("🎓 MBA / GATE",
                                  callback_data="cat_mba")],
            [InlineKeyboardButton("📚 Semester / Other",
                                  callback_data="cat_semester")],
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

    # Category selected
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
            [InlineKeyboardButton("🏢 Campus Placements",
                                  callback_data="cat_campus")],
            [InlineKeyboardButton("📋 Government Exams",
                                  callback_data="cat_govt")],
            [InlineKeyboardButton("🏥 Medical Entrance",
                                  callback_data="cat_medical")],
            [InlineKeyboardButton("🔬 Engineering Entrance",
                                  callback_data="cat_engineering")],
            [InlineKeyboardButton("🎓 MBA / GATE",
                                  callback_data="cat_mba")],
            [InlineKeyboardButton("📚 Semester / Other",
                                  callback_data="cat_semester")],
        ]
        await query.edit_message_text(
            "📚 *Select your exam category:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    # Exam selected
    elif data.startswith("exam_"):
        exam = data.replace("exam_", "")
        conn = get_conn()
        c = conn.cursor()
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

    # Time selected
    elif data.startswith("time_"):
        study_time = data.replace("time_", "")
        conn = get_conn()
        c = conn.cursor()
        c.execute("""UPDATE temp_registration
                     SET study_time=? WHERE user_id=?""",
                  (study_time, user.id))

        # Also update directly if already registered
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

    # Language selected — Complete registration
    elif data.startswith("lang_"):
        language = data.replace("lang_", "")

        conn = get_conn()
        c = conn.cursor()

        c.execute("""SELECT exam, study_time FROM temp_registration
                     WHERE user_id=?""", (user.id,))
        reg = c.fetchone()

        if not reg or not reg[0] or not reg[1]:
            await query.edit_message_text(
                "❌ *Session expired!*\n\nPlease use /start again.",
                parse_mode="Markdown"
            )
            conn.close()
            return

        exam, study_time = reg

        c.execute("""INSERT OR REPLACE INTO users
            (user_id, username, first_name, exam, study_time, language)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user.id, user.username, user.first_name,
             exam, study_time, language))
        conn.commit()

        # Find match — exclude blocked users
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
                         FROM users WHERE user_id=?""", (partner_id,))
            partner_row = c.fetchone()
            partner_name = partner_row[0] if partner_row else "Study Partner"
            partner_username = partner_row[1] if partner_row else None
            partner_language = partner_row[2] if partner_row else "Unknown"

            now = datetime.now(INDIA_TZ).isoformat()
            c.execute("""UPDATE users SET partner_id=?, matched_at=?
                         WHERE user_id=?""", (partner_id, now, user.id))
            c.execute("""UPDATE users SET partner_id=?, matched_at=?
                         WHERE user_id=?""", (user.id, now, partner_id))
            c.execute("DELETE FROM waiting_queue WHERE user_id=?",
                      (partner_id,))
            c.execute("""INSERT INTO pending_groups
                         (user1_id, user2_id, matched_at)
                         VALUES (?, ?, ?)""", (user.id, partner_id, now))
            c.execute("DELETE FROM temp_registration WHERE user_id=?",
                      (user.id,))
            conn.commit()
            conn.close()

            partner_display = f"@{partner_username}" \
                if partner_username else partner_name
            user_display = f"@{user.username}" \
                if user.username else user.first_name

            # Notify Student 1
            await context.bot.send_message(
                chat_id=user.id,
                text=f"🎉 *You've been matched!*\n\n"
                     f"👥 *Your Study Partner:*\n"
                     f"👤 Name: {partner_name}\n"
                     f"📱 Username: {partner_display}\n"
                     f"📚 Exam: {exam}\n"
                     f"⏰ Study Time: {study_time}\n"
                     f"🗣 Language: {partner_language}\n\n"
                     f"📢 Admin will create your private group soon!\n\n"
                     f"• /checkin — Mark daily study\n"
                     f"• /streak — Your stats\n"
                     f"• /partner — Partner details\n"
                     f"• /rules — How it works",
                parse_mode="Markdown"
            )

            # Notify Student 2
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"🎉 *You've been matched!*\n\n"
                     f"👥 *Your Study Partner:*\n"
                     f"👤 Name: {user.first_name}\n"
                     f"📱 Username: {user_display}\n"
                     f"📚 Exam: {exam}\n"
                     f"⏰ Study Time: {study_time}\n"
                     f"🗣 Language: {language}\n\n"
                     f"📢 Admin will create your private group soon!\n\n"
                     f"• /checkin — Mark daily study\n"
                     f"• /streak — Your stats\n"
                     f"• /partner — Partner details\n"
                     f"• /rules — How it works",
                parse_mode="Markdown"
            )

            # Detailed Admin Notification
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"🎯 *NEW MATCH — ACTION REQUIRED!*\n\n"
                     f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     f"👤 *Student 1:*\n"
                     f"   Name: {user.first_name}\n"
                     f"   Username: {user_display}\n"
                     f"   ID: `{user.id}`\n"
                     f"   Language: {language}\n\n"
                     f"👤 *Student 2:*\n"
                     f"   Name: {partner_name}\n"
                     f"   Username: {partner_display}\n"
                     f"   ID: `{partner_id}`\n"
                     f"   Language: {partner_language}\n\n"
                     f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     f"📚 *Exam:* {exam}\n"
                     f"⏰ *Study Time:* {study_time}\n"
                     f"🕐 *Matched:* "
                     f"{datetime.now(INDIA_TZ).strftime('%d %b %Y, %I:%M %p')}\n\n"
                     f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     f"✅ *Steps:*\n"
                     f"1️⃣ Create a private Telegram group\n"
                     f"2️⃣ Add {user_display}\n"
                     f"3️⃣ Add {partner_display}\n"
                     f"4️⃣ Add @{context.bot.username} as admin\n"
                     f"5️⃣ Type /group_ready in that group\n\n"
                     f"Or use /send_invite {user.id} {partner_id} "
                     f"to send invite links directly!",
                parse_mode="Markdown"
            )

            await query.edit_message_text(
                f"🎉 *Registration complete!*\n\n"
                f"✅ *Matched with {partner_name}!*\n\n"
                f"📢 Admin will send your group invite soon!\n\n"
                f"Check your messages for partner details! 👆",
                parse_mode="Markdown"
            )

        else:
            c.execute("""INSERT OR REPLACE INTO waiting_queue
                (user_id, exam, study_time, language, joined_at)
                VALUES (?, ?, ?, ?, ?)""",
                (user.id, exam, study_time, language,
                 datetime.now(INDIA_TZ).isoformat()))
            c.execute("DELETE FROM temp_registration WHERE user_id=?",
                      (user.id,))
            conn.commit()

            # Check queue position
            c.execute("""SELECT COUNT(*) FROM waiting_queue
                         WHERE exam=? AND study_time=?""",
                      (exam, study_time))
            position = c.fetchone()[0]
            conn.close()

            await query.edit_message_text(
                f"✅ *Registration complete!*\n\n"
                f"📚 *Exam:* {exam}\n"
                f"⏰ *Study Time:* {study_time}\n"
                f"🗣 *Language:* {language}\n\n"
                f"⏳ *Looking for your study partner...*\n"
                f"📊 Queue position: #{position}\n\n"
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
        message = f"🔄 *Streak reset!* New streak: 1 day\n⚠️ *Reputation:* -5 points"

    reputation = max(0, min(100, reputation))

    c.execute("""UPDATE users SET streak=?, last_checkin=?, reputation=?
                 WHERE user_id=?""",
              (streak, today_date.strftime("%Y-%m-%d"), reputation, user_id))
    conn.commit()
    conn.close()

    # Milestone messages
    milestone_msg = ""
    if streak == 7:
        milestone_msg = "\n\n🎉 *Amazing! 7-day streak! One week strong!*"
    elif streak == 30:
        milestone_msg = "\n\n🏆 *Incredible! 30-day streak! You're unstoppable!*"
    elif streak == 100:
        milestone_msg = "\n\n💎 *LEGENDARY! 100-day streak! You are a PrepRoom Champion!*"

    await update.message.reply_text(
        f"✅ *Check-in recorded!*\n\n{message}\n\n"
        f"📊 *Total Reputation:* {reputation}/100"
        f"{milestone_msg}",
        parse_mode="Markdown"
    )

    if partner_id:
        await context.bot.send_message(
            chat_id=partner_id,
            text=f"👀 *{update.effective_user.first_name} just checked in!*\n\n"
                 f"Don't fall behind — use /checkin now! 💪",
            parse_mode="Markdown"
        )

    if group_id:
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=f"✅ *{update.effective_user.first_name}* checked in!\n"
                     f"🔥 Streak: *{streak}* days",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Group notification failed: {e}")

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
        "• +2 per check-in\n"
        "• -5 per missed day\n"
        "• 🥉Bronze → 🥈Silver → 🥇Gold → 💎Diamond\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👻 *Ghost Rules*\n"
        "• Day 1 missed = Reminder at 12PM\n"
        "• Day 2 missed = Warning at 12PM\n"
        "• Day 3 missed = -15 rep + reassigned\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 *Commands*\n"
        "• /help — All commands\n"
        "• /checkin — Mark today studied\n"
        "• /streak — Your stats\n"
        "• /profile — Full profile\n"
        "• /partner — Partner details\n"
        "• /leaderboard — Top 10\n"
        "• /report — Report partner\n"
        "• /leave — Leave partner\n"
        "• /block — Block partner\n"
        "• /edit — Change details\n"
        "• /feedback — Send feedback\n\n"
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
        f"⚠️ *Report submitted!*\n\n"
        f"Admin will review within 24 hours. 💪",
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"🚨 *INACTIVITY REPORT*\n\n"
             f"📢 *By:* User `{user_id}`\n"
             f"👤 *Reported:* {partner_name} (`{partner_id}`)\n\n"
             f"📝 Investigate and reassign if needed.",
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
                     f"🔥 *Current Streak:* {streak} days\n"
                     f"⭐ *Reputation:* {reputation}/100\n"
                     f"🏆 *Tier:* {tier}\n\n"
                     f"💪 Keep going this week!\n"
                     f"Use /leaderboard to see your rank!",
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
                 partner_id, reputation, streak FROM users
                 WHERE banned=0""")
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
                         f"Don't break your *{streak} day streak!* 🔥\n\n"
                         f"Use /checkin now! 💪",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Day 1 reminder failed: {e}")

        elif missed == 2:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ *{first_name}, you've missed 2 days!*\n\n"
                         f"Use /checkin now!\n\n"
                         f"⚠️ One more day missed:\n"
                         f"• -15 reputation points\n"
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
                         f"Missed 3+ days.\n\n"
                         f"• Reputation: -15 points\n"
                         f"• Partner reassigned\n\n"
                         f"Use /start to find new partner! 💪",
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
                        text=f"😔 *Your partner was inactive 3+ days.*\n\n"
                             f"Use /start to rematch! 💪",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Partner msg failed: {e}")

                c.execute("""SELECT wq.user_id FROM waiting_queue wq
                             WHERE wq.exam=(
                                 SELECT exam FROM users WHERE user_id=?)
                             AND wq.study_time=(
                                 SELECT study_time FROM users WHERE user_id=?)
                             LIMIT 1""", (partner_id, partner_id))
                new_match = c.fetchone()

                if new_match:
                    new_partner_id = new_match[0]
                    now = datetime.now(INDIA_TZ).isoformat()
                    c.execute("""UPDATE users SET partner_id=?, matched_at=?
                                 WHERE user_id=?""",
                              (new_partner_id, now, partner_id))
                    c.execute("""UPDATE users SET partner_id=?, matched_at=?
                                 WHERE user_id=?""",
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
                    text=f"👻 *GHOST DETECTED!*\n\n"
                         f"👤 {first_name} (ID: `{user_id}`)\n"
                         f"📉 Reputation: -15\n"
                         f"🔄 Partner reassigned",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Admin ghost msg failed: {e}")

    conn.commit()
    conn.close()

# ================= ADMIN: SEND INVITE =================
async def send_invite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text(
            "❌ *Invalid user IDs!*",
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

    if not match:
        await update.message.reply_text(
            "❌ *No pending match found for these users!*",
            parse_mode="Markdown")
        conn.close()
        return

    match_id = match[0]

    try:
        # Create invite link for the group
        # Admin must first create the group and add bot as admin
        # Then use this command in that group
        chat_id = update.effective_chat.id

        if chat_id == ADMIN_USER_ID:
            await update.message.reply_text(
                "⚠️ *Please use this command inside the group you created!*\n\n"
                "Steps:\n"
                "1. Create group\n"
                "2. Add both students\n"
                "3. Add bot as admin\n"
                "4. Type /send_invite [id1] [id2] inside the group",
                parse_mode="Markdown"
            )
            conn.close()
            return

        # Create invite link
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=chat_id,
            member_limit=2,
            name=f"PrepRoom Match #{match_id}"
        )

        link = invite_link.invite_link

        # Update group_id for both users
        c.execute("""UPDATE users SET group_id=?
                     WHERE user_id IN (?, ?)""", (chat_id, u1, u2))
        c.execute("""UPDATE pending_groups SET status='done'
                     WHERE match_id=?""", (match_id,))
        conn.commit()
        conn.close()

        # Send invite to both students
        await context.bot.send_message(
            chat_id=u1,
            text=f"🎉 *Your study group is ready!*\n\n"
                 f"Click below to join your private study group:\n\n"
                 f"👉 {link}\n\n"
                 f"This link is only for you! 🔒",
            parse_mode="Markdown"
        )

        await context.bot.send_message(
            chat_id=u2,
            text=f"🎉 *Your study group is ready!*\n\n"
                 f"Click below to join your private study group:\n\n"
                 f"👉 {link}\n\n"
                 f"This link is only for you! 🔒",
            parse_mode="Markdown"
        )

        await update.message.reply_text(
            f"✅ *Invite links sent to both students!*\n\n"
            f"Group linked successfully! 🎉",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Send invite failed: {e}")
        await update.message.reply_text(
            f"❌ *Error sending invite:* {str(e)}\n\n"
            f"Make sure bot is admin in the group!",
            parse_mode="Markdown"
        )

# ================= ADMIN: GROUP READY =================
async def group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT match_id, user1_id, user2_id
                 FROM pending_groups WHERE status='pending' LIMIT 1""")
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
        "✅ *Group linked!*\n\n"
        "Students can now use /checkin here!",
        parse_mode="Markdown"
    )

# ================= ADMIN: PENDING =================
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT pg.match_id, pg.user1_id, pg.user2_id,
                 pg.matched_at, u1.first_name, u2.first_name
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
        msg += f"🔹 *Match #{m[0]}*\n"
        msg += f"   👤 {m[4]} (`{m[1]}`)\n"
        msg += f"   👤 {m[5]} (`{m[2]}`)\n"
        msg += f"   🕐 {m[3][:16]}\n"
        msg += f"   👉 /send_invite {m[1]} {m[2]}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= ADMIN: USERS =================
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    c.execute("""SELECT COUNT(*) FROM users
                 WHERE last_checkin=?""",
              (today().strftime("%Y-%m-%d"),))
    checked_today = c.fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"📊 *PrepRoom Stats*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Total Users:* {total}\n"
        f"🤝 *Matched:* {matched}\n"
        f"⏳ *Waiting:* {waiting}\n"
        f"✅ *Checked in Today:* {checked_today}\n"
        f"🚫 *Banned:* {banned}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )

# ================= ADMIN: FIND USER =================
async def find_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("❌ *Invalid user ID!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT first_name, username, exam, study_time,
                 language, streak, reputation, last_checkin,
                 partner_id, banned, warnings
                 FROM users WHERE user_id=?""", (target_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(
            "❌ *User not found!*",
            parse_mode="Markdown")
        return

    name, username, exam, study_time, language, streak, \
        reputation, last_checkin, partner_id, banned, warnings = row

    username_display = f"@{username}" if username else "Not set"
    tier = get_tier(reputation)
    status = "🚫 Banned" if banned else "✅ Active"

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
        f"⚠️ *Warnings:* {warnings}\n"
        f"🔰 *Status:* {status}",
        parse_mode="Markdown"
    )

# ================= ADMIN: REMATCH =================
async def rematch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("❌ *Invalid user ID!*",
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
            f"✅ *User rematched successfully!*\n\n"
            f"New partner ID: `{new_partner_id}`",
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
                text="🎉 *You have a new study partner!*\n\n"
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
            f"⏳ *No match found right now.*\n\n"
            f"User added to waiting queue.",
            parse_mode="Markdown"
        )

# ================= ADMIN: BAN =================
async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("❌ *Invalid user ID!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET banned=1 WHERE user_id=?", (target_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🚫 *User `{target_id}` has been banned.*",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="🚫 *You have been banned from PrepRoom.*\n\n"
                 "Contact admin if you think this is a mistake.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ban notification failed: {e}")

# ================= ADMIN: UNBAN =================
async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("❌ *Invalid user ID!*",
                                        parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET banned=0 WHERE user_id=?", (target_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ *User `{target_id}` has been unbanned.*",
        parse_mode="Markdown"
    )

# ================= ADMIN: BROADCAST =================
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                text=f"📢 *Message from PrepRoom Admin:*\n\n{message}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast failed for {user_id}: {e}")

    await update.message.reply_text(
        f"✅ *Broadcast complete!*\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}",
        parse_mode="Markdown"
    )

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
    print("=" * 50)

    setup_db()

    app = Application.builder().token(TOKEN).build()

    job_queue = app.job_queue

    # Daily morning reminder — 8AM IST
    job_queue.run_daily(
        morning_reminder,
        time=dtime(hour=8, minute=0, second=0, tzinfo=INDIA_TZ)
    )

    # Daily ghost check — 12PM IST
    job_queue.run_daily(
        daily_check,
        time=dtime(hour=12, minute=0, second=0, tzinfo=INDIA_TZ)
    )

    # Weekly report — Every Sunday 9AM IST
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

    # Admin commands
    app.add_handler(CommandHandler("group_ready", group_ready))
    app.add_handler(CommandHandler("send_invite", send_invite_cmd))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("find", find_cmd))
    app.add_handler(CommandHandler("rematch", rematch_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))

    # Callback and message handlers
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_feedback))

    print("🎯 Bot is running!")
    print("=" * 50)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
