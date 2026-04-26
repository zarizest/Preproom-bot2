import os
import sqlite3
import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIGURATION =================
TOKEN = os.getenv("TOKEN", "8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "8456901459"))

DB_NAME = "preproom.db"

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
    
    # Users table
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
    
    # Waiting queue table
    c.execute("""CREATE TABLE IF NOT EXISTS waiting_queue (
        user_id INTEGER PRIMARY KEY,
        exam TEXT,
        study_time TEXT,
        language TEXT,
        joined_at TEXT
    )""")
    
    # Pending groups table
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
    return datetime.utcnow().date()

def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date() if d else None

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
        logger.info(f"User {user.id} selected exam: {exam}")
        
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
        logger.info(f"User {user.id} selected study time: {study_time}")
        
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
        exam = context.user_data.get("exam")
        study_time = context.user_data.get("study_time")
        
        logger.info(f"User {user.id} completed registration: {exam} | {study_time} | {language}")
        
        conn = get_conn()
        c = conn.cursor()
        
        # Save user
        c.execute("""INSERT OR REPLACE INTO users 
            (user_id, username, first_name, exam, study_time, language)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user.id, user.username, user.first_name, exam, study_time, language))
        
        # Check for match
        c.execute("""SELECT user_id, first_name FROM waiting_queue 
                     WHERE exam=? AND study_time=? AND user_id!=?""",
                  (exam, study_time, user.id))
        match = c.fetchone()
        
        if match:
            partner_id, partner_name = match
            now = datetime.utcnow().isoformat()
            
            # Link partners
            c.execute("UPDATE users SET partner_id=?, matched_at=? WHERE user_id=?", (partner_id, now, user.id))
            c.execute("UPDATE users SET partner_id=?, matched_at=? WHERE user_id=?", (user.id, now, partner_id))
            c.execute("DELETE FROM waiting_queue WHERE user_id=?", (partner_id,))
            c.execute("""INSERT INTO pending_groups (user1_id, user2_id, matched_at)
                         VALUES (?, ?, ?)""", (user.id, partner_id, now))
            conn.commit()
            conn.close()
            
            # Notify users
            await context.bot.send_message(
                chat_id=user.id,
                text=f"🎉 *You've been matched with {partner_name}!*\n\n"
                     f"📢 Admin will create your private study group within 24 hours.\n\n"
                     f"⏳ *While you wait:*\n"
                     f"• Use /checkin daily\n"
                     f"• Use /streak to track progress\n"
                     f"• Use /partner to see partner details",
                parse_mode="Markdown"
            )
            
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"🎉 *You've been matched with {user.first_name}!*\n\n"
                     f"📢 Admin will create your private study group within 24 hours.\n\n"
                     f"⏳ *While you wait:*\n"
                     f"• Use /checkin daily\n"
                     f"• Use /streak to track progress\n"
                     f"• Use /partner to see partner details",
                parse_mode="Markdown"
            )
            
            # Notify admin
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
                     f"4. Type /group_ready in the group",
                parse_mode="Markdown"
            )
            
            await query.edit_message_text(
                f"🎉 *Registration complete!*\n\n"
                f"✅ Matched with *{partner_name}*\n\n"
                f"Admin will create your study group soon!",
                parse_mode="Markdown"
            )
            
        else:
            # Add to waiting queue
            c.execute("""INSERT INTO waiting_queue 
                (user_id, exam, study_time, language, joined_at)
                VALUES (?, ?, ?, ?, ?)""",
                (user.id, exam, study_time, language, datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()
            
            await query.edit_message_text(
                f"✅ *Registration complete!*\n\n"
                f"⏳ *Looking for a study partner...*\n"
                f"You'll be notified when matched!\n\n"
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
        await update.message.reply_text("✅ *Already checked in today!* Come back tomorrow.", parse_mode="Markdown")
        conn.close()
        return
    
    # Streak and reputation logic
    if last == today_date - timedelta(days=1):
        streak += 1
        reputation += 2
        message = f"🔥 *Streak:* {streak} days (+1)\n⭐ *Reputation:* +2"
    else:
        streak = 1
        reputation -= 5
        message = f"🔄 *Streak reset!* New streak: 1 day\n⚠️ *Reputation:* -5"
    
    reputation = max(0, min(100, reputation))
    
    c.execute("""UPDATE users SET streak=?, last_checkin=?, reputation=? 
                 WHERE user_id=?""",
              (streak, today_date.strftime("%Y-%m-%d"), reputation, user_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ *Check-in recorded!*\n\n{message}\n\n📊 *Current:* {reputation}/100 reputation",
        parse_mode="Markdown"
    )
    
    # Notify partner
    if partner_id:
        await context.bot.send_message(
            chat_id=partner_id,
            text=f"👀 *{update.effective_user.first_name} just checked in!*\n\nDon't fall behind - use /checkin",
            parse_mode="Markdown"
        )
    
    # Notify group
    if group_id:
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=f"✅ *{update.effective_user.first_name}* checked in!\n🔥 Current streak: *{streak}* days",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send group notification: {e}")

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
    
    # Determine tier
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
• Check-in before midnight (UTC)
• Your partner gets notified when you check in

━━━━━━━━━━━━━━━━━━━━━━

🔥 *Streaks*
• +1 streak for each consecutive day
• Miss a day? Streak resets to 0
• Long streaks = Bragging rights!

━━━━━━━━━━━━━━━━━━━━━━

⭐ *Reputation System*
• Start at 40 reputation
• +2 reputation for each check-in
• -5 reputation for missing a day
• Earn tiers: Bronze → Silver → Gold → Diamond

━━━━━━━━━━━━━━━━━━━━━━

👻 *Inactivity Rules*
• Missing 2+ days = Partner can /report you
• Admin reviews and may reassign partners
• Always inform your partner if you need a break

━━━━━━━━━━━━━━━━━━━━━━

📊 *Commands*
• `/streak` - View your stats
• `/partner` - See partner details
• `/checkin` - Mark today as studied
• `/rules` - Show this again
• `/report` - Report inactive partner

━━━━━━━━━━━━━━━━━━━━━━

💪 *Remember*
Consistency beats perfection. Study a little every day!

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
        f"⚠️ *Report submitted for {partner_name}*\n\n"
        f"Admin will review this report within 24 hours.\n\n"
        f"Thank you for maintaining accountability!",
        parse_mode="Markdown"
    )
    
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"🚨 *INACTIVITY REPORT*\n\n"
             f"📢 *Reported by:* User `{user_id}`\n"
             f"👤 *Reported partner:* {partner_name} (ID: `{partner_id}`)\n\n"
             f"📝 *Action required:* Investigate and take appropriate action.",
        parse_mode="Markdown"
    )
    
    logger.info(f"Report: User {user_id} reported partner {partner_id}")

# ================= ADMIN: GROUP READY =================
async def group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only command!*", parse_mode="Markdown")
        return
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT match_id, user1_id, user2_id FROM pending_groups WHERE status='pending' LIMIT 1")
    match = c.fetchone()
    
    if not match:
        await update.message.reply_text("ℹ️ *No pending matches* to process.", parse_mode="Markdown")
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
        f"Both students can now use this group for /checkin and daily motivation!",
        parse_mode="Markdown"
    )
    
    logger.info(f"Admin linked group {group_id} for users {u1} and {u2}")

# ================= ADMIN: PENDING MATCHES =================
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only command!*", parse_mode="Markdown")
        return
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT match_id, user1_id, user2_id, matched_at FROM pending_groups WHERE status='pending'")
    matches = c.fetchall()
    conn.close()
    
    if not matches:
        await update.message.reply_text("✅ *No pending matches.* Great job!", parse_mode="Markdown")
        return
    
    msg = "📋 *Pending Matches to Process:*\n\n"
    for m in matches:
        msg += f"🔹 *Match #{m[0]}*\n"
        msg += f"   User1: `{m[1]}` | User2: `{m[2]}`\n"
        msg += f"   Matched: {m[3]}\n\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= MAIN FUNCTION =================
def main():
    print("=" * 50)
    print("🚀 PREPROOM ACCOUNTABILITY BOT")
    print("=" * 50)
    
    # Check environment variables
    if not TOKEN:
        logger.error("❌ TOKEN environment variable not set!")
        print("ERROR: Please set TOKEN in Railway environment variables")
        return
    
    if ADMIN_USER_ID == 0:
        logger.error("❌ ADMIN_USER_ID environment variable not set!")
        print("ERROR: Please set ADMIN_USER_ID in Railway environment variables")
        print("Get your ID from @userinfobot on Telegram")
        return
    
    print(f"✅ Bot Token: {TOKEN[:10]}...")
    print(f"✅ Admin ID: {ADMIN_USER_ID}")
    print("=" * 50)
    
    # Setup database
    setup_db()
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CommandHandler("partner", partner_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("group_ready", group_ready))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Run bot
    print("🎯 PrepRoom Bot is running! Press Ctrl+C to stop")
    print("=" * 50)
    logger.info("🚀 PrepRoom Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
