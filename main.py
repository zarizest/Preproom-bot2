import os
import sqlite3
import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN", "8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "8456901459"))

DB_NAME = "preproom.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PrepRoom")

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
        status TEXT DEFAULT "pending"
    )""")
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def today():
    return datetime.utcnow().date()

def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date() if d else None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("TCS NQT", callback_data="exam_TCS NQT")],
        [InlineKeyboardButton("Infosys", callback_data="exam_Infosys")],
        [InlineKeyboardButton("SSC CGL", callback_data="exam_SSC CGL")],
        [InlineKeyboardButton("UPSC", callback_data="exam_UPSC")],
        [InlineKeyboardButton("Banking", callback_data="exam_Banking")],
    ]
    await update.message.reply_text(
        "👋 *Welcome to PrepRoom!*\n\n📚 Which exam are you preparing for?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("exam_"):
        context.user_data["exam"] = data.replace("exam_", "")
        keyboard = [
            [InlineKeyboardButton("Morning", callback_data="time_Morning")],
            [InlineKeyboardButton("Afternoon", callback_data="time_Afternoon")],
            [InlineKeyboardButton("Evening", callback_data="time_Evening")],
            [InlineKeyboardButton("Night", callback_data="time_Night")],
        ]
        await query.edit_message_text("⏰ Select study time:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("time_"):
        context.user_data["study_time"] = data.replace("time_", "")
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang_English")],
            [InlineKeyboardButton("Hindi", callback_data="lang_Hindi")],
            [InlineKeyboardButton("Marathi", callback_data="lang_Marathi")],
        ]
        await query.edit_message_text("🗣 Select language:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("lang_"):
        user = query.from_user
        language = data.replace("lang_", "")
        exam = context.user_data["exam"]
        study_time = context.user_data["study_time"]

        conn = get_conn()
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO users 
            (user_id, username, first_name, exam, study_time, language)
            VALUES (?, ?, ?, ?, ?, ?)""",
                  (user.id, user.username, user.first_name, exam, study_time, language))

        c.execute("""SELECT user_id FROM waiting_queue 
                     WHERE exam=? AND study_time=? AND user_id!=?""",
                  (exam, study_time, user.id))
        match = c.fetchone()

        if match:
            partner_id = match[0]
            now = datetime.utcnow().isoformat()
            c.execute("UPDATE users SET partner_id=?, matched_at=? WHERE user_id=?", (partner_id, now, user.id))
            c.execute("UPDATE users SET partner_id=?, matched_at=? WHERE user_id=?", (user.id, now, partner_id))
            c.execute("DELETE FROM waiting_queue WHERE user_id=?", (partner_id,))
            c.execute("""INSERT INTO pending_groups (user1_id, user2_id, matched_at)
                         VALUES (?, ?, ?)""", (user.id, partner_id, now))
            conn.commit()
            conn.close()

            await context.bot.send_message(
                chat_id=user.id,
                text="🎉 You've been matched! Admin will create group soon.",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=partner_id,
                text="🎉 You've been matched! Admin will create group soon.",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"""🎯 *NEW MATCH!*

Student 1: {user.first_name} (ID: `{user.id}`)
Student 2: ID `{partner_id}`

Exam: {exam}
Time: {study_time}

👉 Create group + /group_ready""",
                parse_mode="Markdown"
            )
        else:
            c.execute("""INSERT INTO waiting_queue 
                (user_id, exam, study_time, language, joined_at)
                VALUES (?, ?, ?, ?, ?)""",
                      (user.id, exam, study_time, language, datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()
            await query.edit_message_text("⏳ Waiting for a partner...")

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT streak, last_checkin, partner_id, group_id, reputation FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row:
        await update.message.reply_text("❌ Use /start first")
        conn.close()
        return

    streak, last_checkin, partner_id, group_id, reputation = row
    last = parse_date(last_checkin)
    today_date = today()

    if last == today_date:
        await update.message.reply_text("✅ Already checked in today")
        conn.close()
        return

    if last == today_date - timedelta(days=1):
        streak += 1
        reputation += 2
    else:
        streak = 1
        reputation -= 5

    reputation = max(0, min(100, reputation))

    c.execute("""UPDATE users SET streak=?, last_checkin=?, reputation=? 
                 WHERE user_id=?""",
              (streak, today_date.strftime("%Y-%m-%d"), reputation, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🔥 *Streak:* {streak} days\n⭐ *Reputation:* {reputation}/100", parse_mode="Markdown")

    if partner_id:
        await context.bot.send_message(
            chat_id=partner_id,
            text="👀 *Your partner just checked in!* Don't fall behind. Use /checkin",
            parse_mode="Markdown"
        )
    if group_id:
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=f"✅ *{update.effective_user.first_name}* checked in! (🔥 {streak} day streak)",
                parse_mode="Markdown"
            )
        except:
            pass

async def streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT streak, reputation FROM users WHERE user_id=?", (update.effective_user.id,))
    row = c.fetchone()
    conn.close()

    if row:
        await update.message.reply_text(f"🔥 *Streak:* {row[0]} days\n⭐ *Reputation:* {row[1]}/100", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Use /start first")

async def partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT partner_id FROM users WHERE user_id=?", (update.effective_user.id,))
    row = c.fetchone()

    if not row or not row[0]:
        await update.message.reply_text("⏳ No partner yet. Waiting for match...")
        conn.close()
        return

    c.execute("SELECT first_name, streak FROM users WHERE user_id=?", (row[0],))
    p = c.fetchone()
    conn.close()

    if p:
        await update.message.reply_text(f"👥 *Partner:* {p[0]}\n🔥 *Their streak:* {p[1]} days", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Partner not found")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📋 *PrepRoom Rules*

✅ *Daily Check-in:* /checkin
• +2 reputation for consecutive days
• -5 reputation if you miss a day

🔥 *Streaks reset if you miss 1 day*

⭐ *Reputation starts at 40*
• 0-49: Bronze
• 50-74: Silver
• 75-89: Gold
• 90-100: Diamond

👻 *Inactive 2+ days?* Partner can /report you

💪 *Your partner is counting on you. Stay consistent!*
"""
    await update.message.reply_text(rules_text, parse_mode="Markdown")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT partner_id, first_name FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row or not row[0]:
        await update.message.reply_text("❌ No partner to report!")
        return

    partner_id, partner_name = row
    await update.message.reply_text(f"⚠️ Report submitted for *{partner_name}*. Admin will review.", parse_mode="Markdown")
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"⚠️ *INACTIVITY REPORT*\n\nUser `{user_id}` reported partner `{partner_id}`\n\nInvestigate and take action.",
        parse_mode="Markdown"
    )

async def group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Admin only command!")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT match_id, user1_id, user2_id FROM pending_groups WHERE status='pending' LIMIT 1")
    match = c.fetchone()

    if not match:
        await update.message.reply_text("No pending matches")
        conn.close()
        return

    match_id, u1, u2 = match
    group_id = update.effective_chat.id

    c.execute("UPDATE users SET group_id=? WHERE user_id IN (?, ?)", (group_id, u1, u2))
    c.execute("UPDATE pending_groups SET status='done' WHERE match_id=?", (match_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Group linked successfully!")

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Admin only!")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT match_id, user1_id, user2_id FROM pending_groups WHERE status='pending'")
    matches = c.fetchall()
    conn.close()

    if not matches:
        await update.message.reply_text("✅ No pending matches.")
        return

    msg = "📋 *Pending Matches:*\n\n"
    for m in matches:
        msg += f"Match #{m[0]}: User {m[1]} & User {m[2]}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

def main():
    if not TOKEN:
        logger.error("❌ TOKEN environment variable not set!")
        return
    if ADMIN_USER_ID == 0:
        logger.error("❌ ADMIN_USER_ID environment variable not set!")
        return

    setup_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("streak", streak))
    app.add_handler(CommandHandler("partner", partner))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("group_ready", group_ready))
    app.add_handler(CommandHandler("pending", pending))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("🚀 PrepRoom Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
