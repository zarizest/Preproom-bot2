import os
import sqlite3
import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIGURATION =================
TOKEN = os.getenv("TOKEN","8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI")
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
        status TEXT DEFAULT 'active'
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

# ================= START COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("🏢 TCS NQT", callback_data="exam_TCS NQT")],
        [InlineKeyboardButton("🏢 Infosys", callback_data="exam_Infosys")],
        [InlineKeyboardButton("🏢 Wipro", callback_data="exam_Wipro")],
        [InlineKeyboardButton("📋 UPSC", callback_data="exam_UPSC")],
        [InlineKeyboardButton("📋 Banking", callback_data="exam_Banking")],
        [InlineKeyboardButton("📋 SSC CGL", callback_data="exam_SSC CGL")],
        [InlineKeyboardButton("🏥 NEET", callback_data="exam_NEET")],
        [InlineKeyboardButton("🔬 JEE", callback_data="exam_JEE")],
        [InlineKeyboardButton("🎓 CAT/GATE", callback_data="exam_CAT")],
        [InlineKeyboardButton("📚 Semester", callback_data="exam_Semester")],
        [InlineKeyboardButton("📚 Other", callback_data="exam_Other")],
    ]
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n📚 *Select your exam:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= BUTTON HANDLER =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    username = query.from_user.username
    
    print(f"🔘 Clicked: {data}")
    
    # ========== EXAM SELECTION ==========
    if data.startswith("exam_"):
        exam = data.replace("exam_", "")
        exam = exam.replace("_", " ")
        context.user_data['exam'] = exam
        print(f"   Exam saved: {exam}")
        
        keyboard = [
            [InlineKeyboardButton("🌅 Early Morning (5-8 AM)", callback_data="time_5_8")],
            [InlineKeyboardButton("☀️ Morning (8 AM-12 PM)", callback_data="time_8_12")],
            [InlineKeyboardButton("🌤️ Afternoon (12-4 PM)", callback_data="time_12_16")],
            [InlineKeyboardButton("🌆 Evening (4-8 PM)", callback_data="time_16_20")],
            [InlineKeyboardButton("🌙 Night (8 PM-12 AM)", callback_data="time_20_24")],
            [InlineKeyboardButton("🦉 Late Night (12-3 AM)", callback_data="time_0_3")],
        ]
        await query.edit_message_text(
            f"✅ Exam: *{exam}*\n\n⏰ *Select your study time:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    # ========== TIME SELECTION ==========
    if data.startswith("time_"):
        time_slot = data.replace("time_", "")
        time_display = {
            '5_8': 'Early Morning (5-8 AM)',
            '8_12': 'Morning (8 AM-12 PM)',
            '12_16': 'Afternoon (12-4 PM)',
            '16_20': 'Evening (4-8 PM)',
            '20_24': 'Night (8 PM-12 AM)',
            '0_3': 'Late Night (12-3 AM)'
        }.get(time_slot, time_slot)
        
        context.user_data['time'] = time_display
        print(f"   Time saved: {time_display}")
        
        keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_English")],
            [InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi")],
            [InlineKeyboardButton("🇮🇳 Marathi", callback_data="lang_Marathi")],
            [InlineKeyboardButton("🇮🇳 Tamil", callback_data="lang_Tamil")],
            [InlineKeyboardButton("🇮🇳 Telugu", callback_data="lang_Telugu")],
            [InlineKeyboardButton("🇮🇳 Bengali", callback_data="lang_Bengali")],
            [InlineKeyboardButton("🇮🇳 Kannada", callback_data="lang_Kannada")],
            [InlineKeyboardButton("🇮🇳 Malayalam", callback_data="lang_Malayalam")],
        ]
        await query.edit_message_text(
            f"✅ Exam: *{context.user_data['exam']}*\n"
            f"✅ Time: *{time_display}*\n\n"
            f"🗣️ *Select your preferred language:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    # ========== LANGUAGE SELECTION ==========
    if data.startswith("lang_"):
        language = data.replace("lang_", "")
        exam = context.user_data.get('exam', 'Unknown')
        study_time = context.user_data.get('time', 'Unknown')
        
        print(f"   Language saved: {language}")
        print(f"   FINAL: {user_name} | {exam} | {study_time} | {language}")
        
        # Save to database
        conn = get_conn()
        c = conn.cursor()
        
        c.execute("""INSERT OR REPLACE INTO users 
            (user_id, username, first_name, exam, study_time, language, reputation, streak, status)
            VALUES (?, ?, ?, ?, ?, ?, 40, 0, 'active')""",
            (user_id, username, user_name, exam, study_time, language))
        conn.commit()
        
        # Check for match
        c.execute("""SELECT user_id, first_name, username FROM waiting_queue 
                     WHERE exam = ? AND study_time = ? AND user_id != ?
                     ORDER BY joined_at ASC LIMIT 1""",
                  (exam, study_time, user_id))
        match = c.fetchone()
        
        if match:
            partner_id, partner_name, partner_username = match
            now = datetime.utcnow().isoformat()
            
            print(f"   🎯 MATCH FOUND: {user_name} <-> {partner_name}")
            
            c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
                     (partner_id, now, user_id))
            c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
                     (user_id, now, partner_id))
            c.execute("DELETE FROM waiting_queue WHERE user_id = ?", (partner_id,))
            c.execute("""INSERT INTO pending_groups (user1_id, user2_id, matched_at, status)
                         VALUES (?, ?, ?, 'pending')""", (user_id, partner_id, now))
            conn.commit()
            conn.close()
            
            # Admin notification
            admin_msg = f"🎯 NEW MATCH!\n\n👤 {user_name} (ID: {user_id})\n👤 {partner_name} (ID: {partner_id})\n📚 {exam}\n⏰ {study_time}\n\nCreate group and use /group_ready"
            try:
                await context.bot.send_message(chat_id=ADMIN_USER_ID, text=admin_msg)
            except Exception as e:
                print(f"   Admin notify failed: {e}")
            
            # Notify users
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 *Matched with {partner_name}!*\n\nAdmin will create your study group soon!\n\nUse /checkin daily! 🔥",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"🎉 *Matched with {user_name}!*\n\nAdmin will create your study group soon!\n\nUse /checkin daily! 🔥",
                parse_mode="Markdown"
            )
            
            await query.edit_message_text(
                f"🎉 *Matched with {partner_name}!*\n\nAdmin will create your group soon!\n\nUse /checkin to start your streak! 🔥",
                parse_mode="Markdown"
            )
        else:
            # Add to waiting queue
            c.execute("""INSERT OR REPLACE INTO waiting_queue 
                (user_id, exam, study_time, language, joined_at)
                VALUES (?, ?, ?, ?, ?)""",
                (user_id, exam, study_time, language, datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()
            
            await query.edit_message_text(
                f"✅ *Registration complete!*\n\n"
                f"📚 *Exam:* {exam}\n"
                f"⏰ *Time:* {study_time}\n"
                f"🗣 *Language:* {language}\n\n"
                f"⏳ *Looking for a study partner...*\n"
                f"You'll be notified when matched!\n\n"
                f"Use /checkin to start your streak! 🔥",
                parse_mode="Markdown"
            )
        
        print(f"   ✅ Registration complete for {user_name}")
        return

# ================= CHECKIN COMMAND =================
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_date = today()
    
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
    
    if last == today_date:
        await update.message.reply_text("✅ Already checked in today!")
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
    
    await update.message.reply_text(f"✅ *Checked in!*\n🔥 Streak: {streak} days\n⭐ Reputation: {reputation}/100", parse_mode="Markdown")
    
    if partner_id:
        await context.bot.send_message(chat_id=partner_id, text=f"👀 *{update.effective_user.first_name} just checked in!* Use /checkin", parse_mode="Markdown")
    
    if group_id:
        try:
            await context.bot.send_message(chat_id=group_id, text=f"✅ *{update.effective_user.first_name}* checked in! 🔥", parse_mode="Markdown")
        except:
            pass

# ================= STREAK COMMAND =================
async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT first_name, streak, reputation FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        await update.message.reply_text("❌ Use /start first")
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
    
    await update.message.reply_text(f"📊 *{name}*\n🔥 Streak: {streak} days\n⭐ Reputation: {reputation}/100\n🏆 Tier: {tier}", parse_mode="Markdown")

# ================= PARTNER COMMAND =================
async def partner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    
    if not row or not row[0]:
        await update.message.reply_text("⏳ No partner yet. Waiting for match...", parse_mode="Markdown")
        conn.close()
        return
    
    partner_id = row[0]
    c.execute("SELECT first_name, streak, reputation FROM users WHERE user_id=?", (partner_id,))
    partner = c.fetchone()
    conn.close()
    
    if partner:
        await update.message.reply_text(f"👥 *Partner:* {partner[0]}\n🔥 Streak: {partner[1]} days", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Partner not found")

# ================= RULES COMMAND =================
async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📋 *PrepRoom Rules*

✅ /checkin - Daily check-in
• +2 rep for consecutive days
• -5 rep if you miss

🔥 Streaks reset if you miss 1 day

⭐ Start at 40 rep
• Bronze: 0-49
• Silver: 50-74
• Gold: 75-89
• Diamond: 90-100

👻 Ghost detection after 2 days missing

💪 Your partner is counting on you!
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
        await update.message.reply_text("❌ No partner to report!")
        return
    
    partner_id, partner_name = row
    
    await update.message.reply_text(f"⚠️ Report submitted for {partner_name}. Admin will review.")
    await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"🚨 REPORT: User {user_id} reported {partner_id}")

# ================= ADMIN COMMANDS =================
async def group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Admin only!")
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
    
    await update.message.reply_text("✅ Group linked!")

async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT match_id, user1_id, user2_id, matched_at FROM pending_groups WHERE status='pending'")
    matches = c.fetchall()
    conn.close()
    
    if not matches:
        await update.message.reply_text("No pending matches")
        return
    
    msg = "📋 Pending Matches:\n\n"
    for m in matches:
        msg += f"Match #{m[0]}: User {m[1]} & User {m[2]}\n"
    await update.message.reply_text(msg)

# ================= GHOST DETECTION =================
async def check_ghosts(context: ContextTypes.DEFAULT_TYPE):
    print(f"🕐 Running ghost detection")
    
    conn = get_conn()
    c = conn.cursor()
    two_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    c.execute("""
        SELECT user_id, partner_id, first_name, reputation 
        FROM users 
        WHERE (last_checkin < ? OR last_checkin IS NULL)
        AND partner_id IS NOT NULL AND status = 'active'
    """, (two_days_ago,))
    
    ghosts = c.fetchall()
    
    for ghost_id, partner_id, ghost_name, reputation in ghosts:
        new_reputation = max(0, reputation - 15)
        
        c.execute("UPDATE users SET reputation = ?, partner_id = NULL, status = 'ghosted' WHERE user_id = ?", 
                 (new_reputation, ghost_id))
        c.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (partner_id,))
        
        try:
            await context.bot.send_message(chat_id=ghost_id, text=f"👻 You've been marked inactive! -15 reputation")
        except:
            pass
    
    conn.commit()
    conn.close()
    print(f"   Processed {len(ghosts)} ghosts")

# ================= MAIN =================
def main():
    print("=" * 50)
    print("🚀 PREPROOM BOT - WORKING VERSION")
    print("=" * 50)
    
    if not TOKEN:
        print("❌ TOKEN not set!")
        return
    
    if ADMIN_USER_ID == 0:
        print("❌ ADMIN_USER_ID not set!")
        return
    
    setup_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # Schedule ghost detection (every 24 hours)
    if app.job_queue:
        app.job_queue.run_repeating(check_ghosts, interval=86400, first=30)
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CommandHandler("partner", partner_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("group_ready", group_ready))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Bot is running!")
    print("📋 Commands: /start, /checkin, /streak, /partner, /rules, /report")
    print("👑 Admin: /group_ready, /pending")
    
    app.run_polling()

if __name__ == "__main__":
    main()
