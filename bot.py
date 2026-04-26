import os
import sqlite3
import logging
from datetime import datetime, timedelta, time as dtime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIGURATION =================
TOKEN = os.getenv("TOKEN", "8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "8456901459"))

DB_NAME = "preproom.db"
INDIA_TZ = pytz.timezone("Asia/Kolkata")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PrepRoom")

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
        matched_at TEXT
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

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📚 TCS NQT", callback_data="exam_TCS NQT")],
        [InlineKeyboardButton("📚 Infosys", callback_data="exam_Infosys")],
        [InlineKeyboardButton("📚 SSC CGL", callback_data="exam_SSC CGL")],
        [InlineKeyboardButton("📚 UPSC", callback_data="exam_UPSC")],
        [InlineKeyboardButton("📚 Banking", callback_data="exam_Banking")],
    ]
    await update.message.reply_text(
        "👋 *Welcome to PrepRoom!*\n\n"
        "I'll match you with a study partner.\n\n"
        "📚 *Which exam are you preparing for?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= BUTTON HANDLER =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data.startswith("exam_"):
        exam = data.replace("exam_", "")

        conn = get_conn()
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO temp_registration 
                     (user_id, exam) VALUES (?, ?)""",
                  (user.id, exam))
        conn.commit()
        conn.close()

        keyboard = [
            [InlineKeyboardButton("🌅 Morning (6AM-10AM)", callback_data="time_Morning")],
            [InlineKeyboardButton("☀️ Afternoon (12PM-4PM)", callback_data="time_Afternoon")],
            [InlineKeyboardButton("🌙 Evening (6PM-10PM)", callback_data="time_Evening")],
            [InlineKeyboardButton("🌃 Night (10PM-2AM)", callback_data="time_Night")],
        ]
        await query.edit_message_text(
            f"✅ *Exam:* {exam}\n\n⏰ *When do you usually study?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("time_"):
        study_time = data.replace("time_", "")

        conn = get_conn()
        c = conn.cursor()
        c.execute("""UPDATE temp_registration 
                     SET study_time=? WHERE user_id=?""",
                  (study_time, user.id))
        conn.commit()
        conn.close()

        keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_English")],
            [InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi")],
            [InlineKeyboardButton("🇮🇳 Marathi", callback_data="lang_Marathi")],
        ]
        await query.edit_message_text(
            f"✅ *Study time:* {study_time}\n\n🗣 *Preferred language?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

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

        c.execute("""SELECT user_id FROM waiting_queue
                     WHERE exam=? AND study_time=? AND user_id!=?""",
                  (exam, study_time, user.id))
        match = c.fetchone()

        if match:
            partner_id = match[0]
            c.execute("""SELECT first_name FROM users 
                         WHERE user_id=?""", (partner_id,))
            name_row = c.fetchone()
            partner_name = name_row[0] if name_row else "Study Partner"

            now = datetime.now(INDIA_TZ).isoformat()
            c.execute("""UPDATE users SET partner_id=?, matched_at=? 
                         WHERE user_id=?""", (partner_id, now, user.id))
            c.execute("""UPDATE users SET partner_id=?, matched_at=? 
                         WHERE user_id=?""", (user.id, now, partner_id))
            c.execute("""DELETE FROM waiting_queue 
                         WHERE user_id=?""", (partner_id,))
            c.execute("""INSERT INTO pending_groups 
                         (user1_id, user2_id, matched_at)
                         VALUES (?, ?, ?)""", (user.id, partner_id, now))
            c.execute("""DELETE FROM temp_registration 
                         WHERE user_id=?""", (user.id,))
            conn.commit()
            conn.close()

            await query.edit_message_text(
                f"🎉 *Registration complete!*\n\n"
                f"✅ Matched with *{partner_name}*\n\n"
                f"Admin will create your study group soon!\n\n"
                f"Use /rules to learn how PrepRoom works! 📖",
                parse_mode="Markdown"
            )

            await context.bot.send_message(
                chat_id=user.id,
                text=f"🎉 *You've been matched with {partner_name}!*\n\n"
                     f"📢 Admin will create your private study group within 24 hours.\n\n"
                     f"⏳ *While you wait:*\n"
                     f"• Use /checkin daily\n"
                     f"• Use /streak to track progress\n"
                     f"• Use /partner to see partner details\n"
                     f"• Use /rules to learn the system",
                parse_mode="Markdown"
            )

            await context.bot.send_message(
                chat_id=partner_id,
                text=f"🎉 *You've been matched with {user.first_name}!*\n\n"
                     f"📢 Admin will create your private study group within 24 hours.\n\n"
                     f"⏳ *While you wait:*\n"
                     f"• Use /checkin daily\n"
                     f"• Use /streak to track progress\n"
                     f"• Use /partner to see partner details\n"
                     f"• Use /rules to learn the system",
                parse_mode="Markdown"
            )

            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"🎯 *NEW MATCH!*\n\n"
                     f"👤 *Student 1:* {user.first_name} (ID: `{user.id}`)\n"
                     f"👤 *Student 2:* {partner_name} (ID: `{partner_id}`)\n"
                     f"📚 *Exam:* {exam}\n"
                     f"⏰ *Time:* {study_time}\n"
                     f"🗣 *Language:* {language}\n\n"
                     f"✅ *Action Required:*\n"
                     f"1. Create a private Telegram group\n"
                     f"2. Add BOTH students\n"
                     f"3. Add @{context.bot.username} as admin\n"
                     f"4. Type /group_ready in that group",
                parse_mode="Markdown"
            )

        else:
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
                f"⏰ *Time:* {study_time}\n"
                f"🗣 *Language:* {language}\n\n"
                f"⏳ *Looking for your study partner...*\n"
                f"You will be notified when matched!\n\n"
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

    await update.message.reply_text(
        f"✅ *Check-in recorded!*\n\n{message}\n\n"
        f"📊 *Total Reputation:* {reputation}/100",
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
                     f"🔥 Current streak: *{streak}* days",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Group notification failed: {e}")

# ================= MORNING REMINDER =================
async def morning_reminder(context):
    logger.info("Running morning reminder...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, first_name FROM users")
    users = c.fetchall()
    conn.close()

    for user_id, first_name in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🌅 *Good Morning {first_name}!*\n\n"
                     f"A new day = a new chance to stay consistent! 💪\n\n"
                     f"📚 Study hard today and don't forget:\n"
                     f"✅ Use /checkin after studying!\n\n"
                     f"Your partner is counting on you! 🔥",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Morning reminder failed for {user_id}: {e}")

# ================= DAILY CHECK + GHOST DETECTION =================
async def daily_check(context):
    logger.info("Running daily check...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT user_id, first_name, last_checkin,
                 partner_id, reputation, streak FROM users""")
    users = c.fetchall()

    for user_id, first_name, last_checkin, partner_id, reputation, streak in users:
        missed = days_missed(last_checkin)

        if missed == 1:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ *Hey {first_name}!*\n\n"
                         f"You haven't checked in today!\n\n"
                         f"Don't break your streak of *{streak} days!* 🔥\n\n"
                         f"Use /checkin now! 💪",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Day 1 reminder failed for {user_id}: {e}")

        elif missed == 2:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ *{first_name}, you've missed 2 days!*\n\n"
                         f"Come back now:\n"
                         f"✅ Use /checkin to restart!\n\n"
                         f"⚠️ *Warning:* Miss one more day and:\n"
                         f"• -15 reputation points\n"
                         f"• Partner reassignment\n\n"
                         f"Your partner is waiting! 🙏",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Day 2 warning failed for {user_id}: {e}")

        elif missed >= 3:
            new_rep = max(0, reputation - 15)
            c.execute("""UPDATE users SET reputation=?, partner_id=NULL
                         WHERE user_id=?""", (new_rep, user_id))

            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"👻 *{first_name}, you are marked inactive!*\n\n"
                         f"You missed 3+ days.\n\n"
                         f"*Penalties:*\n"
                         f"• Reputation: -15 points\n"
                         f"• Partner reassigned\n\n"
                         f"Use /start to find a new partner! 💪",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Ghost msg failed for {user_id}: {e}")

            if partner_id:
                c.execute("""UPDATE users SET partner_id=NULL
                             WHERE user_id=?""", (partner_id,))

                try:
                    await context.bot.send_message(
                        chat_id=partner_id,
                        text=f"😔 *Your partner has been inactive 3+ days.*\n\n"
                             f"They have been removed.\n\n"
                             f"🔍 Finding you a new partner!\n\n"
                             f"Use /start to rematch now! 💪",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Partner msg failed for {partner_id}: {e}")

                c.execute("""SELECT wq.user_id FROM waiting_queue wq
                             WHERE wq.exam=(SELECT exam FROM users WHERE user_id=?)
                             AND wq.study_time=(SELECT study_time FROM users WHERE user_id=?)
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
                            text="🎉 *You have a new study partner!*\n\n"
                                 "Use /partner to see details! 💪",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Rematch msg failed: {e}")

            try:
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"👻 *GHOST DETECTED!*\n\n"
                         f"👤 *User:* {first_name} (ID: `{user_id}`)\n"
                         f"📉 *Reputation:* -15 points\n"
                         f"🔄 *Partner reassigned*",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Admin ghost msg failed: {e}")

    conn.commit()
    conn.close()
    logger.info("Daily check complete!")

# ================= STREAK =================
async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT first_name, streak, reputation
                 FROM users WHERE user_id=?""", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(
            "❌ *Not registered!* Use /start first.",
            parse_mode="Markdown")
        return

    name, streak, reputation = row

    if reputation >= 90:
        tier = "💎 Diamond"
    elif reputation >= 75:
        tier = "🥇 Gold"
    elif reputation >= 50:
        tier = "🥈 Silver"
    else:
        tier = "🥉 Bronze"

    await update.message.reply_text(
        f"📊 *{name}'s Stats*\n\n"
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
    c.execute("""SELECT first_name, streak, reputation
                 FROM users WHERE user_id=?""", (partner_id,))
    partner = c.fetchone()
    conn.close()

    if partner:
        await update.message.reply_text(
            f"👥 *Your Study Partner*\n\n"
            f"👤 *Name:* {partner[0]}\n"
            f"🔥 *Streak:* {partner[1]} days\n"
            f"⭐ *Reputation:* {partner[2]}/100\n\n"
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
        "• Partner gets notified when you check in\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔥 *Streaks*\n"
        "• +1 streak each consecutive day\n"
        "• Miss a day = streak resets\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⭐ *Reputation*\n"
        "• Start at 40 points\n"
        "• +2 per check-in\n"
        "• -5 per missed day\n"
        "• Tiers: 🥉Bronze → 🥈Silver → 🥇Gold → 💎Diamond\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👻 *Ghost Rules*\n"
        "• Day 1 missed = Reminder\n"
        "• Day 2 missed = Warning\n"
        "• Day 3 missed = -15 rep + partner reassigned\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 *Commands*\n"
        "• /checkin — Mark today studied\n"
        "• /streak — Your stats\n"
        "• /partner — Partner details\n"
        "• /rules — This message\n"
        "• /report — Report inactive partner\n\n"
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

# ================= ADMIN: GROUP READY =================
async def group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text(
            "❌ *Admin only!*",
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
        "✅ *Group linked successfully!*\n\n"
        "Students can now use /checkin in this group!",
        parse_mode="Markdown"
    )

# ================= ADMIN: PENDING =================
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text(
            "❌ *Admin only!*",
            parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT match_id, user1_id, user2_id, matched_at
                 FROM pending_groups WHERE status='pending'""")
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
        msg += f"   User1: `{m[1]}`\n"
        msg += f"   User2: `{m[2]}`\n"
        msg += f"   Matched: {m[3]}\n\n"

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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CommandHandler("partner", partner_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("group_ready", group_ready))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🎯 Bot is running!")
    print("=" * 50)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
