import os
import sqlite3
import logging
from datetime import datetime, timedelta
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIGURATION =================
TOKEN = os.getenv("TOKEN",  "8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "8456901459"))

DB_NAME = "preproom.db"
INDIA_TZ = pytz.timezone("Asia/Kolkata")

# ================= LOGGING =================
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
        status TEXT DEFAULT "pending"
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

# ================= START COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} ({user.first_name}) started the bot")

    keyboard = [
        [InlineKeyboardButton("📚 TCS NQT", callback_data="exam_TCS NQT")],
        [InlineKeyboardButton("📚 Infosys", callback_data="exam_Infosys")],
        [InlineKeyboardButton("📚 SSC CGL", callback_data="exam_SSC CGL")],
        [InlineKeyboardButton("📚 UPSC", callback_data="exam_UPSC")],
        [InlineKeyboardButton("📚 Banking", callback_data="exam_Banking")],
    ]

    await update.message.reply_text(
        "👋 *Welcome to PrepRoom!*\n\n"
        "I'll match you with a study partner based on your exam.\n\n"
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
        context.user_data["exam"] = exam

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
        context.user_data["study_time"] = study_time

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
        context.user_data["language"] = language

        exam = context.user_data.get("exam")
        study_time = context.user_data.get("study_time")

        conn = get_conn()
        c = conn.cursor()

        c.execute("""INSERT OR REPLACE INTO users
            (user_id, username, first_name, exam, study_time, language)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user.id, user.username, user.first_name, exam, study_time, language))

        c.execute("""SELECT user_id, first_name FROM waiting_queue
                     WHERE exam=? AND study_time=? AND user_id!=?""",
                  (exam, study_time, user.id))
        match = c.fetchone()

        if match:
            partner_id, partner_name = match
            now = datetime.now(INDIA_TZ).isoformat()

            c.execute("UPDATE users SET partner_id=?, matched_at=? WHERE user_id=?", (partner_id, now, user.id))
            c.execute("UPDATE users SET partner_id=?, matched_at=? WHERE user_id=?", (user.id, now, partner_id))
            c.execute("DELETE FROM waiting_queue WHERE user_id=?", (partner_id,))
            c.execute("""INSERT INTO pending_groups (user1_id, user2_id, matched_at)
                         VALUES (?, ?, ?)""", (user.id, partner_id, now))
            conn.commit()
            conn.close()

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

            await query.edit_message_text(
                f"🎉 *Registration complete!*\n\n"
                f"✅ Matched with *{partner_name}*\n\n"
                f"Admin will create your study group soon!\n\n"
                f"Use /rules to learn how PrepRoom works! 📖",
                parse_mode="Markdown"
            )

        else:
            c.execute("""INSERT INTO waiting_queue
                (user_id, exam, study_time, language, joined_at)
                VALUES (?, ?, ?, ?, ?)""",
                (user.id, exam, study_time, language, datetime.now(INDIA_TZ).isoformat()))
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

# ================= CHECKIN COMMAND =================
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_date = today()

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT streak, last_checkin, partner_id, group_id, reputation FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row:
        await update.message.reply_text("❌ *Not registered!* Use /start first.", parse_mode="Markdown")
        conn.close()
        return

    streak, last_checkin, partner_id, group_id, reputation = row
    last = parse_date(last_checkin)

    if last == today_date:
        await update.message.reply_text("✅ *Already checked in today!* Come back tomorrow. 💪", parse_mode="Markdown")
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
            logger.error(f"Failed to send group notification: {e}")

# ================= MORNING REMINDER (8AM) =================
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
                     f"📚 Study hard today and don't forget to:\n"
                     f"✅ Use /checkin after studying\n\n"
                     f"Your partner is counting on you! 🔥",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Morning reminder failed for {user_id}: {e}")

# ================= DAILY CHECK + GHOST DETECTION (12PM) =================
async def daily_check(context):
    logger.info("Running daily check and ghost detection...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT user_id, first_name, last_checkin, 
                 partner_id, reputation, streak 
                 FROM users""")
    users = c.fetchall()

    for user_id, first_name, last_checkin, partner_id, reputation, streak in users:
        missed = days_missed(last_checkin)

        # Day 1 missed — soft reminder
        if missed == 1:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ *Hey {first_name}!*\n\n"
                         f"You haven't checked in today yet!\n\n"
                         f"Don't break your streak of *{streak} days!* 🔥\n\n"
                         f"Use /checkin now — it only takes 1 second! 💪",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Day 1 reminder failed for {user_id}: {e}")

        # Day 2 missed — strong warning
        elif missed == 2:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ *{first_name}, you've missed 2 days!*\n\n"
                         f"Your streak has been reset to 0 😔\n\n"
                         f"But it's not too late! Come back now:\n"
                         f"✅ Use /checkin to restart your journey\n\n"
                         f"⚠️ *Warning:* Missing one more day will result in:\n"
                         f"• -15 reputation points\n"
                         f"• Partner reassignment\n\n"
                         f"Your partner is waiting for you! 🙏",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Day 2 warning failed for {user_id}: {e}")

        # Day 3 missed — ghost detected
        elif missed >= 3:
            new_rep = max(0, reputation - 15)

            c.execute("""UPDATE users SET reputation=?, partner_id=NULL 
                         WHERE user_id=?""", (new_rep, user_id))

            # Notify ghost
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"👻 *{first_name}, you have been marked as inactive!*\n\n"
                         f"You missed 3+ days of check-ins.\n\n"
                         f"*Penalties applied:*\n"
                         f"• Reputation: -{15} points\n"
                         f"• Your partner has been reassigned\n\n"
                         f"Want to start fresh? Use /start to find a new partner! 💪\n\n"
                         f"We hope to see you back! 🙏",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Ghost notification failed for {user_id}: {e}")

            # Handle abandoned partner
            if partner_id:
                c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (partner_id,))

                try:
                    await context.bot.send_message(
                        chat_id=partner_id,
                        text=f"😔 *Your study partner has been inactive for 3+ days.*\n\n"
                             f"They have been removed from your partnership.\n\n"
                             f"🔍 *We are finding you a new partner!*\n\n"
                             f"Use /start to get rematched immediately! 💪",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Partner notification failed for {partner_id}: {e}")

                # Try auto rematch
                c.execute("""SELECT wq.user_id FROM waiting_queue wq
                             JOIN users u ON wq.user_id = u.user_id
                             WHERE wq.exam = (SELECT exam FROM users WHERE user_id=?)
                             AND wq.study_time = (SELECT study_time FROM users WHERE user_id=?)
                             LIMIT 1""",
                          (partner_id, partner_id))
                new_match = c.fetchone()

                if new_match:
                    new_partner_id = new_match[0]
                    now = datetime.now(INDIA_TZ).isoformat()

                    c.execute("UPDATE users SET partner_id=?, matched_at=? WHERE user_id=?",
                              (new_partner_id, now, partner_id))
                    c.execute("UPDATE users SET partner_id=?, matched_at=? WHERE user_id=?",
                              (partner_id, now, new_partner_id))
                    c.execute("DELETE FROM waiting_queue WHERE user_id=?", (new_partner_id,))

                    try:
                        await context.bot.send_message(
                            chat_id=partner_id,
                            text=f"🎉 *Great news! We found you a new partner!*\n\n"
                                 f"Use /partner to see their details.\n"
                                 f"Use /checkin to start fresh! 💪",
                            parse_mode="Markdown"
                        )
                        await context.bot.send_message(
                            chat_id=new_partner_id,
                            text=f"🎉 *You have been matched with a new study partner!*\n\n"
                                 f"Use /partner to see their details.\n"
                                 f"Use /checkin to start! 💪",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Auto rematch notification failed: {e}")

            # Notify admin
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"👻 *GHOST DETECTED!*\n\n"
                         f"👤 *User:* {first_name} (ID: `{user_id}`)\n"
                         f"📉 *Reputation:* -{15} points\n"
                         f"🔄 *Partner reassigned automatically*\n\n"
                         f"No action needed from you.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Admin ghost notification failed: {e}")

    conn.commit()
    conn.close()
    logger.info("Daily check complete!")

# ================= STREAK COMMAND =================
async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT first_name, streak, reputation FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("❌ *Not registered!* Use /start first.", parse_mode="Markdown")
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

# ================= PARTNER COMMAND =================
async def partner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row or not row[0]:
        await update.message.reply_text("⏳ *No partner yet!* Waiting for match...", parse_mode="Markdown")
        conn.close()
        return

    partner_id = row[0]
    c.execute("SELECT first_name, streak, reputation FROM users WHERE user_id=?", (partner_id,))
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
    else:
        await update.message.reply_text("⚠️ *Partner not found* in database.", parse_mode="Markdown")

# ================= RULES COMMAND =================
async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📋 *PrepRoom Accountability Rules*

━━━━━━━━━━━━━━━━━━━━━━

✅ *Daily Check-in*
• Use `/checkin` every day to mark your study session
• Check-in before midnight
• Your partner gets notified when you check in

━━━━━━━━━━━━━━━━━━━━━━

🔥 *Streaks*
• +1 streak for each consecutive day
• Miss a day? Streak resets to 0

━━━━━━━━━━━━━━━━━━━━━━

⭐ *Reputation System*
• Start at 40 reputation
• +2 reputation for each check-in
• -5 reputation for missing a day
• Tiers: 🥉 Bronze → 🥈 Silver → 🥇 Gold → 💎 Diamond

━━━━━━━━━━━━━━━━━━━━━━

👻 *Ghost Rules*
• Day 1 missed = Reminder sent
• Day 2 missed = Warning sent
• Day 3 missed = -15 reputation + partner reassigned

━━━━━━━━━━━━━━━━━━━━━━

📊 *Commands*
• `/checkin` - Mark today as studied
• `/streak` - View your stats
• `/partner` - See partner details
• `/rules` - Show this again
• `/report` - Report inactive partner

━━━━━━━━━━━━━━━━━━━━━━

💪 Consistency beats perfection!
*Your partner is counting on you!* 🔥
"""
    await update.message.reply_text(rules_text, parse_mode="Markdown")

# ================= REPORT COMMAND =================
async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT partner_id, first_name FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row or not row[0]:
        await update.message.reply_text("❌ *No partner to report!*", parse_mode="Markdown")
        return

    partner_id, partner_name = row

    await update.message.reply_text(
        f"⚠️ *Report submitted!*\n\n"
        f"Admin will review within 24 hours.\n\n"
        f"Thank you for maintaining accountability! 💪",
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"🚨 *INACTIVITY REPORT*\n\n"
             f"📢 *Reported by:* User `{user_id}`\n"
             f"👤 *Reported:* {partner_name} (ID: `{partner_id}`)\n\n"
             f"📝 *Action:* Investigate and reassign if needed.",
        parse_mode="Markdown"
    )

# ================= ADMIN: GROUP READY =================
async def group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*", parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT match_id, user1_id, user2_id FROM pending_groups WHERE status='pending' LIMIT 1")
    match = c.fetchone()

    if not match:
        await update.message.reply_text("ℹ️ *No pending matches.*", parse_mode="Markdown")
        conn.close()
        return

    match_id, u1, u2 = match
    group_id = update.effective_chat.id

    c.execute("UPDATE users SET group_id=? WHERE user_id IN (?, ?)", (group_id, u1, u2))
    c.execute("UPDATE pending_groups SET status='done' WHERE match_id=?", (match_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ *Group linked successfully!*\n\n"
        f"Students can now use /checkin in this group!",
        parse_mode="Markdown"
    )

# ================= ADMIN: PENDING MATCHES =================
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*", parse_mode="Markdown")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT match_id, user1_id, user2_id, matched_at FROM pending_groups WHERE status='pending'")
    matches = c.fetchall()
    conn.close()

    if not matches:
        await update.message.reply_text("✅ *No pending matches!*", parse_mode="Markdown")
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
        print("Get your ID from @userinfobot on Telegram")
        return

    print(f"✅ Token loaded")
    print(f"✅ Admin ID: {ADMIN_USER_ID}")
    print("=" * 50)

    setup_db()

    app = Application.builder().token(TOKEN).build()

    # Scheduled jobs
    job_queue = app.job_queue

    # Morning reminder — 8AM India time every day
    job_queue.run_daily(
        morning_reminder,
        time=datetime.now(INDIA_TZ).replace(hour=8, minute=0, second=0).timetz()
    )

    # Daily check + ghost detection — 12PM India time every day
    job_queue.run_daily(
        daily_check,
        time=datetime.now(INDIA_TZ).replace(hour=12, minute=0, second=0).timetz()
    )

    # Handlers
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
