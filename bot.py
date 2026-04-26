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
    logger.info("✅ Database initialized")

def today():
    return datetime.utcnow().date()

def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date() if d else None

# ================= START COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with category selection first."""
    user = update.effective_user
    
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT user_id FROM users WHERE user_id = ?', (user.id,))
    existing = c.fetchone()
    conn.close()
    
    if existing:
        await show_dashboard(update, context)
        return
    
    context.user_data.clear()
    context.user_data['onboarding'] = {'first_name': user.first_name}
    
    keyboard = [
        [InlineKeyboardButton("🏢 Campus Placements (TCS, Infosys, etc.)", callback_data="cat_placements")],
        [InlineKeyboardButton("📋 Government Exams (SSC, Banking, UPSC)", callback_data="cat_government")],
        [InlineKeyboardButton("🏥 Medical Entrance (NEET)", callback_data="exam_NEET")],
        [InlineKeyboardButton("🔬 Engineering Entrance (JEE)", callback_data="exam_JEE")],
        [InlineKeyboardButton("🎓 MBA/GATE", callback_data="cat_mba_gate")],
        [InlineKeyboardButton("📚 Semester / Other", callback_data="cat_semester")],
    ]
    
    await update.message.reply_text(
        f"👋 Welcome to PrepRoom, {user.first_name}!\n\n"
        "🎯 *I'll match you with a study partner.*\n\n"
        "📋 *Step 1/3: What are you preparing for?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user dashboard"""
    user = update.effective_user
    await update.message.reply_text(
        f"📊 *Welcome back, {user.first_name}!*\n\n"
        "Use /checkin to mark today's study\n"
        "Use /streak to see your stats\n"
        "Use /partner to see your partner\n"
        "Use /rules to see the rules",
        parse_mode='Markdown'
    )

# ================= BUTTON HANDLER =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button clicks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    data = query.data
    
    print(f"🔘 Button clicked: '{data}' by user {user_id}")
    
    if 'onboarding' not in context.user_data:
        context.user_data['onboarding'] = {}
    
    # ========== BACK TO START ==========
    if data == 'back_to_start':
        await start(update, context)
        return
    
    # ========== CATEGORY: PLACEMENTS ==========
    if data == 'cat_placements':
        keyboard = [
            [InlineKeyboardButton("TCS NQT", callback_data="exam_TCS NQT")],
            [InlineKeyboardButton("Infosys", callback_data="exam_Infosys")],
            [InlineKeyboardButton("Wipro Elite", callback_data="exam_Wipro")],
            [InlineKeyboardButton("Capgemini", callback_data="exam_Capgemini")],
            [InlineKeyboardButton("Accenture", callback_data="exam_Accenture")],
            [InlineKeyboardButton("Cognizant", callback_data="exam_Cognizant")],
            [InlineKeyboardButton("Other Placement", callback_data="exam_Other")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
        await query.edit_message_text(
            "🏢 *Campus Placements*\nSelect your target company:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # ========== CATEGORY: GOVERNMENT ==========
    if data == 'cat_government':
        keyboard = [
            [InlineKeyboardButton("SSC CGL", callback_data="exam_SSC CGL")],
            [InlineKeyboardButton("SSC CHSL", callback_data="exam_SSC CHSL")],
            [InlineKeyboardButton("Banking (IBPS/SBI)", callback_data="exam_Banking")],
            [InlineKeyboardButton("RRB NTPC", callback_data="exam_RRB")],
            [InlineKeyboardButton("UPSC", callback_data="exam_UPSC")],
            [InlineKeyboardButton("State PSC", callback_data="exam_State PSC")],
            [InlineKeyboardButton("Other Govt Exam", callback_data="exam_Other")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
        await query.edit_message_text(
            "📋 *Government Exams*\nSelect your target exam:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # ========== CATEGORY: MBA/GATE ==========
    if data == 'cat_mba_gate':
        keyboard = [
            [InlineKeyboardButton("CAT / MBA Entrance", callback_data="exam_CAT")],
            [InlineKeyboardButton("GATE", callback_data="exam_GATE")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
        await query.edit_message_text(
            "🎓 *MBA / GATE*\nSelect your exam:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # ========== CATEGORY: SEMESTER ==========
    if data == 'cat_semester':
        keyboard = [
            [InlineKeyboardButton("Semester Exams", callback_data="exam_Semester")],
            [InlineKeyboardButton("Other", callback_data="exam_Other")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
        await query.edit_message_text(
            "📚 *Semester / Other*\nWhat are you studying for?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # ========== EXAM SELECTED ==========
    if data.startswith('exam_'):
        exam = data.replace('exam_', '')
        exam = exam.replace('_', ' ')
        context.user_data['onboarding']['exam'] = exam
        print(f"📚 Exam selected: {exam}")
        
        keyboard = [
            [InlineKeyboardButton("🌅 Early Morning (5-8 AM)", callback_data="time_5_8")],
            [InlineKeyboardButton("☀️ Morning (8 AM-12 PM)", callback_data="time_8_12")],
            [InlineKeyboardButton("🌤️ Afternoon (12-4 PM)", callback_data="time_12_16")],
            [InlineKeyboardButton("🌆 Evening (4-8 PM)", callback_data="time_16_20")],
            [InlineKeyboardButton("🌙 Night (8 PM-12 AM)", callback_data="time_20_24")],
            [InlineKeyboardButton("🦉 Late Night (12-3 AM)", callback_data="time_0_3")],
        ]
        
        await query.edit_message_text(
            f"✅ Exam: *{exam}*\n\n"
            "⏰ *Step 2/3: What's your preferred study time?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # ========== TIME SELECTED ==========
    if data.startswith('time_'):
        time_slot = data.replace('time_', '')
        time_display = {
            '5_8': 'Early Morning (5-8 AM)',
            '8_12': 'Morning (8 AM-12 PM)',
            '12_16': 'Afternoon (12-4 PM)',
            '16_20': 'Evening (4-8 PM)',
            '20_24': 'Night (8 PM-12 AM)',
            '0_3': 'Late Night (12-3 AM)'
        }.get(time_slot, time_slot)
        
        context.user_data['onboarding']['time'] = time_display
        print(f"⏰ Time selected: {time_display}")
        
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
            f"✅ Exam: *{context.user_data['onboarding']['exam']}*\n"
            f"✅ Time: *{time_display}*\n\n"
            "🗣️ *Step 3/3: Click on your preferred language:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # ========== LANGUAGE SELECTED ==========
    if data.startswith('lang_'):
        print(f"🗣️ LANGUAGE SELECTED: {data}")
        
        language = data.replace('lang_', '')
        context.user_data['onboarding']['language'] = language
        
        exam = context.user_data['onboarding'].get('exam', 'Unknown')
        study_time = context.user_data['onboarding'].get('time', 'Unknown')
        
        print(f"📝 COMPLETING REGISTRATION: {user_name} | {exam} | {study_time} | {language}")
        
        # Save to database
        conn = get_conn()
        c = conn.cursor()
        
        c.execute("""INSERT OR REPLACE INTO users 
            (user_id, username, first_name, exam, study_time, language, reputation, streak, status)
            VALUES (?, ?, ?, ?, ?, ?, 40, 0, 'active')""",
            (user_id, query.from_user.username, user_name, exam, study_time, language))
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
            
            print(f"🎯 MATCH FOUND! {user_name} <-> {partner_name}")
            
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
            admin_msg = f"""
🎯 *NEW MATCH ALERT!*

━━━━━━━━━━━━━━━━━━━━━━
👤 *STUDENT 1*
• Name: {user_name}
• Username: @{query.from_user.username or 'No username'}
• User ID: `{user_id}`

👤 *STUDENT 2*
• Name: {partner_name}
• Username: @{partner_username or 'No username'}
• User ID: `{partner_id}`

━━━━━━━━━━━━━━━━━━━━━━
📚 *MATCH DETAILS*
• Exam: {exam}
• Study Time: {study_time}
• Language: {language}

━━━━━━━━━━━━━━━━━━━━━━
✅ *ACTION REQUIRED:*

1️⃣ Create a private Telegram group
2️⃣ Name it: "PrepRoom - {user_name} & {partner_name}"
3️⃣ Add BOTH students
4️⃣ Add @{context.bot.username} as admin
5️⃣ Send /group_ready in the group
"""
            try:
                await context.bot.send_message(chat_id=ADMIN_USER_ID, text=admin_msg, parse_mode="Markdown")
                print(f"   ✅ Admin notified")
            except Exception as e:
                print(f"   ❌ Admin notify failed: {e}")
            
            # Notify users
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 *You've been matched with {partner_name}!*\n\n"
                     f"📢 Admin will create your private study group within 24 hours.\n\n"
                     f"⏳ Use /checkin daily while you wait! 🔥",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"🎉 *You've been matched with {user_name}!*\n\n"
                     f"📢 Admin will create your private study group within 24 hours.\n\n"
                     f"⏳ Use /checkin daily while you wait! 🔥",
                parse_mode="Markdown"
            )
            
            await query.edit_message_text(
                f"🎉 *Registration complete!*\n\n"
                f"✅ Matched with *{partner_name}*\n\n"
                f"Admin will create your study group soon!\n\n"
                f"Use /checkin to start your streak! 🔥",
                parse_mode="Markdown"
            )
            
        else:
            # No match - add to queue
            c.execute("""INSERT OR REPLACE INTO waiting_queue 
                (user_id, exam, study_time, language, joined_at)
                VALUES (?, ?, ?, ?, ?)""",
                (user_id, exam, study_time, language, datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()
            
            print(f"   ⏳ No match - added to waiting queue")
            
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
        
        print(f"✅ Registration completed for {user_name}")
        return
    
    # ========== UNKNOWN ==========
    print(f"⚠️ UNKNOWN CALLBACK: {data}")
    await query.edit_message_text(
        "❌ Something went wrong. Please use /start to begin again.",
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
    
    if partner_id:
        await context.bot.send_message(
            chat_id=partner_id,
            text=f"👀 *{update.effective_user.first_name} just checked in!*\n\nDon't fall behind - use /checkin",
            parse_mode="Markdown"
        )
    
    if group_id:
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=f"✅ *{update.effective_user.first_name}* checked in!\n🔥 Current streak: *{streak}* days",
                parse_mode="Markdown"
            )
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
        f"🏆 *Tier:* {tier}",
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
    c.execute("SELECT first_name, streak, reputation, study_time, exam FROM users WHERE user_id=?", (partner_id,))
    partner = c.fetchone()
    conn.close()
    
    if partner:
        p_name, p_streak, p_reputation, p_time, p_exam = partner
        await update.message.reply_text(
            f"👥 *Your Study Partner*\n\n"
            f"👤 *Name:* {p_name}\n"
            f"📚 *Exam:* {p_exam}\n"
            f"⏰ *Study Time:* {p_time}\n"
            f"🔥 *Streak:* {p_streak} days\n"
            f"⭐ *Reputation:* {p_reputation}/100\n\n"
            f"💬 Motivate each other!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ *Partner not found*", parse_mode="Markdown")

# ================= RULES COMMAND =================
async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📋 *PrepRoom Accountability Rules*

━━━━━━━━━━━━━━━━━━━━━━

✅ *Daily Check-in:* `/checkin`
• +2 reputation for consecutive days
• -5 reputation if you miss a day

━━━━━━━━━━━━━━━━━━━━━━

🔥 *Streaks*
• +1 streak for each consecutive day
• Miss a day? Streak resets to 0
• Long streaks = Bragging rights!

━━━━━━━━━━━━━━━━━━━━━━

⭐ *Reputation System*
• Start at 40 reputation
• +2 per check-in, -5 for missing
• Tiers: Bronze → Silver → Gold → Diamond

━━━━━━━━━━━━━━━━━━━━━━

👻 *Ghost Detection*
• Missing 2+ days = Auto-detected
• -15 reputation penalty
• Partner gets rematched

━━━━━━━━━━━━━━━━━━━━━━

📊 *Commands*
• `/streak` - View your stats
• `/partner` - See partner details
• `/checkin` - Mark today as studied
• `/rules` - Show this again
• `/report` - Report inactive partner

━━━━━━━━━━━━━━━━━━━━━━

💪 *Your partner is counting on you!*
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
        f"⚠️ *Report submitted for {partner_name}*\n\nAdmin will review within 24 hours.",
        parse_mode="Markdown"
    )
    
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"🚨 *INACTIVITY REPORT*\n\nUser `{user_id}` reported partner `{partner_id}`\n\nPartner: {partner_name}",
        parse_mode="Markdown"
    )

# ================= GHOST DETECTION =================
async def check_ghosts(context: ContextTypes.DEFAULT_TYPE):
    """Automatically detect users inactive for 2+ days"""
    print(f"🕐 Running ghost detection at {datetime.utcnow()}")
    
    conn = get_conn()
    c = conn.cursor()
    
    two_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    c.execute("""
        SELECT user_id, partner_id, first_name, reputation 
        FROM users 
        WHERE (last_checkin < ? OR last_checkin IS NULL)
        AND partner_id IS NOT NULL 
        AND status = 'active'
    """, (two_days_ago,))
    
    ghosts = c.fetchall()
    
    for ghost_id, partner_id, ghost_name, reputation in ghosts:
        new_reputation = max(0, reputation - 15)
        
        c.execute("UPDATE users SET reputation = ?, partner_id = NULL, status = 'ghosted' WHERE user_id = ?", 
                 (new_reputation, ghost_id))
        c.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (partner_id,))
        
        try:
            await context.bot.send_message(
                chat_id=ghost_id,
                text=f"👻 *You've been marked as INACTIVE!*\n\n"
                     f"You missed 2+ days of check-ins.\n\n"
                     f"• Reputation: -15 points (now {new_reputation}/100)\n"
                     f"• Your study partner has been reassigned\n\n"
                     f"Use /start to find a new partner! 💪",
                parse_mode="Markdown"
            )
        except:
            pass
        
        try:
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"😔 *Your partner {ghost_name} has been inactive for 2+ days.*\n\n"
                     f"Use /start to find a new partner! 🔥",
                parse_mode="Markdown"
            )
        except:
            pass
        
        # Add partner back to queue
        c.execute("SELECT exam, study_time, language FROM users WHERE user_id=?", (partner_id,))
        partner_data = c.fetchone()
        if partner_data:
            c.execute("""INSERT OR REPLACE INTO waiting_queue 
                        (user_id, exam, study_time, language, joined_at)
                        VALUES (?, ?, ?, ?, ?)""",
                     (partner_id, partner_data[0], partner_data[1], partner_data[2], datetime.utcnow().isoformat()))
    
    conn.commit()
    conn.close()
    print(f"   ✅ Ghost detection completed - Processed {len(ghosts)} ghosts")

# ================= ADMIN COMMANDS =================
async def group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*", parse_mode="Markdown")
        return
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT match_id, user1_id, user2_id FROM pending_groups WHERE status='pending' LIMIT 1")
    match = c.fetchone()
    
    if not match:
        await update.message.reply_text("ℹ️ No pending matches", parse_mode="Markdown")
        conn.close()
        return
    
    match_id, u1, u2 = match
    group_id = update.effective_chat.id
    
    c.execute("UPDATE users SET group_id=? WHERE user_id IN (?, ?)", (group_id, u1, u2))
    c.execute("UPDATE pending_groups SET status='done' WHERE match_id=?", (match_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ *Group linked successfully!*\n\nStudents can now use /checkin in this group!", parse_mode="Markdown")

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
        await update.message.reply_text("✅ No pending matches", parse_mode="Markdown")
        return
    
    msg = "📋 *Pending Matches:*\n\n"
    for m in matches:
        msg += f"🔹 Match #{m[0]}: User {m[1]} & User {m[2]}\n   Matched: {m[3]}\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin broadcast to all users"""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    message = ' '.join(context.args)
    if not message:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    
    sent = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=f"📢 *Announcement:*\n\n{message}", parse_mode="Markdown")
            sent += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users")

# ================= MAIN FUNCTION =================
def main():
    print("=" * 60)
    print("🚀 PREPROOM ACCOUNTABILITY BOT v3.0")
    print("=" * 60)
    
    if not TOKEN:
        print("❌ ERROR: TOKEN environment variable not set!")
        return
    
    if ADMIN_USER_ID == 0:
        print("❌ ERROR: ADMIN_USER_ID environment variable not set!")
        return
    
    print(f"✅ Bot Token: {TOKEN[:15]}...")
    print(f"✅ Admin ID: {ADMIN_USER_ID}")
    print("=" * 60)
    
    setup_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # Schedule ghost detection (every 24 hours)
    if app.job_queue:
        app.job_queue.run_repeating(check_ghosts, interval=86400, first=30)
        print("✅ Ghost detection scheduled (every 24 hours)")
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CommandHandler("partner", partner_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    
    # Admin commands
    app.add_handler(CommandHandler("group_ready", group_ready))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    
    # Callback handler
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("=" * 60)
    print("🎯 PREPROOM BOT IS RUNNING!")
    print("=" * 60)
    print("\n📋 Commands:")
    print("   👤 User: /start, /checkin, /streak, /partner, /rules, /report")
    print("   👑 Admin: /group_ready, /pending, /broadcast")
    print("\n⚡ Features:")
    print("   ✅ Category-based registration (Placements/Govt/MBA/Medical)")
    print("   ✅ Smart matching (Exam + Study Time)")
    print("   ✅ Admin notifications with full details")
    print("   ✅ Streak & Reputation system")
    print("   ✅ Ghost detection (auto -15 rep after 2 days)")
    print("   ✅ Multi-language support (8 languages)")
    print("=" * 60)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
