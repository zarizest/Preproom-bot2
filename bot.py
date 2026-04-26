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
    return datetime.utcnow().date()

def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date() if d else None

def register_user(user_id, username, onboarding_data):
    """Save user to database"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO users 
        (user_id, username, first_name, exam, study_time, language)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, username, onboarding_data.get('first_name', 'User'), 
         onboarding_data.get('exam', 'Unknown'), 
         onboarding_data.get('time', 'Unknown'), 
         onboarding_data.get('language', 'English')))
    conn.commit()
    conn.close()

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
    
    context.user_data['onboarding'] = {'first_name': user.first_name}
    
    keyboard = [
        [InlineKeyboardButton("🏢 Campus Placements (TCS, Infosys, etc.)", callback_data="cat_placements")],
        [InlineKeyboardButton("📋 Government Exams (SSC, Banking, UPSC)", callback_data="cat_government")],
        [InlineKeyboardButton("🏥 Medical Entrance (NEET)", callback_data="exam_NEET")],
        [InlineKeyboardButton("🔬 Engineering Entrance (JEE)", callback_data="exam_JEE")],
        [InlineKeyboardButton("🎓 MBA/GATE", callback_data="cat_mba_gate")],
        [InlineKeyboardButton("📚 Semester / Other", callback_data="cat_semester")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Welcome to PrepRoom, {user.first_name}!\n\n"
        "🎯 *I'll match you with a study partner.*\n\n"
        "📋 *Step 1/3: What are you preparing for?*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user dashboard"""
    await update.message.reply_text(
        "📊 *Your Dashboard*\n\n"
        "Use /checkin to mark today's study\n"
        "Use /streak to see your stats\n"
        "Use /partner to see your partner",
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
    
    # Debug logging
    print(f"🔘 Button clicked: {data} by user {user_id}")
    logger.info(f"Button pressed: {data} by user {user_id}")
    
    if 'onboarding' not in context.user_data:
        context.user_data['onboarding'] = {}
    
    # ========== CATEGORY HANDLERS ==========
    
    if data == 'cat_placements':
        print(f"📂 Category: Placements selected by {user_id}")
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
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🏢 *Campus Placements*\nSelect your target company:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    elif data == 'cat_government':
        print(f"📂 Category: Government selected by {user_id}")
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
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📋 *Government Exams*\nSelect your target exam:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    elif data == 'cat_mba_gate':
        print(f"📂 Category: MBA/GATE selected by {user_id}")
        keyboard = [
            [InlineKeyboardButton("CAT / MBA Entrance", callback_data="exam_CAT")],
            [InlineKeyboardButton("GATE", callback_data="exam_GATE")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎓 *MBA / GATE*\nSelect your exam:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    elif data == 'cat_semester':
        print(f"📂 Category: Semester selected by {user_id}")
        keyboard = [
            [InlineKeyboardButton("Semester Exams", callback_data="exam_Semester")],
            [InlineKeyboardButton("Other", callback_data="exam_Other")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📚 *Semester / Other*\nWhat are you studying for?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    elif data == 'back_to_start':
        print(f"⬅️ Back to start by {user_id}")
        await start(update, context)
        return
    
    # ========== DIRECT EXAMS (NEET, JEE, etc.) ==========
    
    elif data in ['exam_NEET', 'exam_JEE', 'exam_CAT', 'exam_GATE', 'exam_Semester', 'exam_Other']:
        exam = data.replace('exam_', '')
        exam_display = exam.replace('_', ' ')
        context.user_data['onboarding']['exam'] = exam_display
        print(f"📚 Direct exam selected: {exam_display} by {user_id}")
        
        keyboard = [
            [InlineKeyboardButton("🌅 Early Morning (5-8 AM)", callback_data="time_5_8")],
            [InlineKeyboardButton("☀️ Morning (8 AM-12 PM)", callback_data="time_8_12")],
            [InlineKeyboardButton("🌤️ Afternoon (12-4 PM)", callback_data="time_12_16")],
            [InlineKeyboardButton("🌆 Evening (4-8 PM)", callback_data="time_16_20")],
            [InlineKeyboardButton("🌙 Night (8 PM-12 AM)", callback_data="time_20_24")],
            [InlineKeyboardButton("🦉 Late Night (12-3 AM)", callback_data="time_0_3")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Exam: *{exam_display}*\n\n"
            "⏰ *Step 2/3: What's your preferred study time?*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # ========== COMPANY EXAMS ==========
    
    elif data.startswith('exam_') and data not in ['exam_NEET', 'exam_JEE', 'exam_CAT', 'exam_GATE', 'exam_Semester', 'exam_Other']:
        exam = data.replace('exam_', '')
        exam_display = exam.replace('_', ' ')
        context.user_data['onboarding']['exam'] = exam_display
        print(f"🏢 Company exam selected: {exam_display} by {user_id}")
        
        keyboard = [
            [InlineKeyboardButton("🌅 Early Morning (5-8 AM)", callback_data="time_5_8")],
            [InlineKeyboardButton("☀️ Morning (8 AM-12 PM)", callback_data="time_8_12")],
            [InlineKeyboardButton("🌤️ Afternoon (12-4 PM)", callback_data="time_12_16")],
            [InlineKeyboardButton("🌆 Evening (4-8 PM)", callback_data="time_16_20")],
            [InlineKeyboardButton("🌙 Night (8 PM-12 AM)", callback_data="time_20_24")],
            [InlineKeyboardButton("🦉 Late Night (12-3 AM)", callback_data="time_0_3")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Exam: *{exam_display}*\n\n"
            "⏰ *Step 2/3: What's your preferred study time?*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # ========== TIME SELECTED ==========
    
    elif data.startswith('time_'):
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
        context.user_data['onboarding']['time_slot'] = time_slot
        print(f"⏰ Time selected: {time_display} by {user_id}")
        
        keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_English")],
            [InlineKeyboardButton("🇮🇳 हिंदी (Hindi)", callback_data="lang_Hindi")],
            [InlineKeyboardButton("🇮🇳 मराठी (Marathi)", callback_data="lang_Marathi")],
            [InlineKeyboardButton("🇮🇳 தமிழ் (Tamil)", callback_data="lang_Tamil")],
            [InlineKeyboardButton("🇮🇳 తెలుగు (Telugu)", callback_data="lang_Telugu")],
            [InlineKeyboardButton("🇮🇳 বাংলা (Bengali)", callback_data="lang_Bengali")],
            [InlineKeyboardButton("🇮🇳 ಕನ್ನಡ (Kannada)", callback_data="lang_Kannada")],
            [InlineKeyboardButton("🇮🇳 മലയാളം (Malayalam)", callback_data="lang_Malayalam")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Exam: *{context.user_data['onboarding']['exam']}*\n"
            f"✅ Time: *{time_display}*\n\n"
            "🗣️ *Step 3/3: Preferred language for partner chat?*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # ========== LANGUAGE SELECTED - COMPLETE REGISTRATION ==========
    
    elif data.startswith('lang_'):
        print(f"🗣️ Language button detected: {data} by {user_id}")
        
        # Extract language (remove 'lang_' prefix and any parentheses)
        language_raw = data.replace('lang_', '')
        # Remove anything in parentheses like (Hindi)
        language = language_raw.split(' ')[0] if ' ' in language_raw else language_raw
        context.user_data['onboarding']['language'] = language
        
        # Get values from onboarding
        exam = context.user_data['onboarding'].get('exam', 'Unknown')
        study_time = context.user_data['onboarding'].get('time', 'Unknown')
        
        print(f"📝 Completing registration for {user_name}:")
        print(f"   📚 Exam: {exam}")
        print(f"   ⏰ Time: {study_time}")
        print(f"   🗣️ Language: {language}")
        
        # Save user to database
        conn = get_conn()
        c = conn.cursor()
        
        # Check if user already exists
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        existing = c.fetchone()
        
        if existing:
            print(f"   ℹ️ User {user_id} already exists, updating...")
            c.execute("""UPDATE users 
                SET username = ?, first_name = ?, exam = ?, study_time = ?, language = ?
                WHERE user_id = ?""",
                (query.from_user.username, user_name, exam, study_time, language, user_id))
        else:
            print(f"   ✅ Creating new user {user_id}")
            c.execute("""INSERT INTO users 
                (user_id, username, first_name, exam, study_time, language, reputation, streak)
                VALUES (?, ?, ?, ?, ?, ?, 40, 0)""",
                (user_id, query.from_user.username, user_name, exam, study_time, language))
        
        conn.commit()
        
        # Check for match in waiting queue
        print(f"   🔍 Checking for match with exam='{exam}' and time='{study_time}'")
        c.execute("""SELECT user_id, first_name, username FROM waiting_queue 
                     WHERE exam = ? AND study_time = ? AND user_id != ?
                     ORDER BY joined_at ASC LIMIT 1""",
                  (exam, study_time, user_id))
        match = c.fetchone()
        
        if match:
            partner_id, partner_name, partner_username = match
            now = datetime.utcnow().isoformat()
            
            print(f"   🎯 MATCH FOUND! {user_name} <-> {partner_name}")
            
            # Link partners
            c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
                     (partner_id, now, user_id))
            c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
                     (user_id, now, partner_id))
            c.execute("DELETE FROM waiting_queue WHERE user_id = ?", (partner_id,))
            c.execute("""INSERT INTO pending_groups (user1_id, user2_id, matched_at, status)
                         VALUES (?, ?, ?, 'pending')""", (user_id, partner_id, now))
            conn.commit()
            conn.close()
            
            # ========== SEND ADMIN NOTIFICATION ==========
            admin_message = f"""
🎯 *NEW MATCH ALERT!*

━━━━━━━━━━━━━━━━━━━━━━
👤 *STUDENT 1*
• Name: {user_name}
• Username: @{query.from_user.username if query.from_user.username else 'No username'}
• User ID: `{user_id}`

👤 *STUDENT 2*
• Name: {partner_name}
• Username: @{partner_username if partner_username else 'No username'}
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
3️⃣ Add BOTH students to the group
4️⃣ Add @{context.bot.username} as admin
5️⃣ Send /group_ready in the group

━━━━━━━━━━━━━━━━━━━━━━
⏰ *Match Time:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
            
            # Send admin notification
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=admin_message,
                    parse_mode="Markdown"
                )
                print(f"   ✅ Admin notification sent to {ADMIN_USER_ID}")
            except Exception as e:
                print(f"   ❌ Failed to send admin notification: {e}")
            
            # Notify users
            await context.bot.send_message(
                chat_id=user_id,
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
                text=f"🎉 *You've been matched with {user_name}!*\n\n"
                     f"📢 Admin will create your private study group within 24 hours.\n\n"
                     f"⏳ *While you wait:*\n"
                     f"• Use /checkin daily\n"
                     f"• Use /streak to track progress\n"
                     f"• Use /partner to see partner details",
                parse_mode="Markdown"
            )
            
            await query.edit_message_text(
                f"🎉 *Registration complete!*\n\n"
                f"✅ Matched with *{partner_name}*\n\n"
                f"Admin will create your study group soon!\n\n"
                f"Use /streak to track your progress! 🔥",
                parse_mode="Markdown"
            )
            
        else:
            # No match found - add to waiting queue
            print(f"   ⏳ No match found - adding {user_name} to waiting queue")
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
                f"⏳ *Looking for your study partner...*\n"
                f"You will be notified when matched!\n\n"
                f"📖 Use /rules to learn how this works.\n"
                f"🔥 Use /checkin to start your streak!",
                parse_mode="Markdown"
            )
        
        print(f"   ✅ Registration completed for {user_name}")
        return
    
    else:
        # Unknown callback data
        print(f"⚠️ Unknown callback data: {data} from user {user_id}")
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
    c.execute("SELECT first_name, streak, reputation FROM users WHERE user_id=?", (partner_id,))
    partner = c.fetchone()
    conn.close()
    
    if partner:
        await update.message.reply_text(
            f"👥 *Your Study Partner*\n\n"
            f"👤 *Name:* {partner[0]}\n"
            f"🔥 *Streak:* {partner[1]} days\n"
            f"⭐ *Reputation:* {partner[2]}/100",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ *Partner not found*", parse_mode="Markdown")

# ================= RULES COMMAND =================
async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📋 *PrepRoom Accountability Rules*

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
        f"⚠️ *Report submitted for {partner_name}*\n\nAdmin will review.",
        parse_mode="Markdown"
    )
    
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"🚨 *INACTIVITY REPORT*\n\nUser `{user_id}` reported partner `{partner_id}`",
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
        await update.message.reply_text("ℹ️ No pending matches", parse_mode="Markdown")
        conn.close()
        return
    
    match_id, u1, u2 = match
    group_id = update.effective_chat.id
    
    c.execute("UPDATE users SET group_id=? WHERE user_id IN (?, ?)", (group_id, u1, u2))
    c.execute("UPDATE pending_groups SET status='done' WHERE match_id=?", (match_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ Group linked successfully!")

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
        await update.message.reply_text("✅ No pending matches", parse_mode="Markdown")
        return
    
    msg = "📋 *Pending Matches:*\n\n"
    for m in matches:
        msg += f"Match #{m[0]}: User {m[1]} & User {m[2]}\nMatched: {m[3]}\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= GHOST DETECTION =================
async def check_ghosts(context: ContextTypes.DEFAULT_TYPE):
    """Automatically detect users inactive for 2+ days and penalize them"""
    print(f"🕐 Running ghost detection at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info("Running ghost detection check")
    
    conn = get_conn()
    c = conn.cursor()
    
    two_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    # Find users who haven't checked in for 2+ days and have a partner
    c.execute("""
        SELECT user_id, partner_id, first_name, reputation, last_checkin
        FROM users 
        WHERE (last_checkin < ? OR last_checkin IS NULL)
        AND partner_id IS NOT NULL 
        AND status = 'active'
    """, (two_days_ago,))
    
    ghosts = c.fetchall()
    
    if not ghosts:
        print("   ✅ No ghosts found - all users active!")
        logger.info("No ghosts found")
        conn.close()
        return
    
    print(f"   👻 Found {len(ghosts)} ghost(s) to process")
    
    for ghost_id, partner_id, ghost_name, reputation, last_checkin in ghosts:
        # Calculate penalty
        new_reputation = max(0, reputation - 15)
        days_inactive = (datetime.utcnow() - datetime.strptime(last_checkin, "%Y-%m-%d")).days if last_checkin else 99
        
        print(f"   Processing ghost: {ghost_name} (ID: {ghost_id}) - Inactive for {days_inactive} days")
        
        # Remove partner from ghost and apply penalty
        c.execute("""
            UPDATE users 
            SET reputation = ?, partner_id = NULL, status = 'ghosted' 
            WHERE user_id = ?
        """, (new_reputation, ghost_id))
        
        # Remove partner from other user
        c.execute("""
            UPDATE users 
            SET partner_id = NULL 
            WHERE user_id = ?
        """, (partner_id,))
        
        # Notify ghost
        try:
            await context.bot.send_message(
                chat_id=ghost_id,
                text=f"👻 *You've been marked as INACTIVE!*\n\n"
                     f"You missed {days_inactive} days of check-ins.\n\n"
                     f"• Reputation: -15 points (now {new_reputation}/100)\n"
                     f"• Your study partner has been reassigned\n\n"
                     f"Use /start to find a new partner and rebuild your streak! 💪",
                parse_mode="Markdown"
            )
            print(f"      ✅ Notified ghost {ghost_name}")
        except Exception as e:
            logger.error(f"Could not notify ghost {ghost_id}: {e}")
        
        # Notify partner
        try:
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"😔 *Your study partner {ghost_name} has been inactive for {days_inactive} days.*\n\n"
                     f"Don't worry! We'll find you a new partner.\n\n"
                     f"Use /start to get rematched immediately! 🔥",
                parse_mode="Markdown"
            )
            print(f"      ✅ Notified partner {partner_id}")
        except Exception as e:
            logger.error(f"Could not notify partner {partner_id}: {e}")
        
        # Try to find a new match for the partner
        c.execute("SELECT exam, study_time, first_name FROM users WHERE user_id=?", (partner_id,))
        partner_data = c.fetchone()
        
        if partner_data:
            partner_exam, partner_time, partner_name = partner_data
            
            # Find another user in waiting queue
            c.execute("""
                SELECT user_id, first_name FROM waiting_queue 
                WHERE exam = ? AND study_time = ? 
                LIMIT 1
            """, (partner_exam, partner_time))
            
            new_match = c.fetchone()
            
            if new_match:
                new_partner_id, new_partner_name = new_match
                
                print(f"      🔄 Rematching {partner_name} with {new_partner_name}")
                
                # Link new partners
                now = datetime.utcnow().isoformat()
                c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
                         (new_partner_id, now, partner_id))
                c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
                         (partner_id, now, new_partner_id))
                c.execute("DELETE FROM waiting_queue WHERE user_id = ?", (new_partner_id,))
                
                # Create new pending group
                c.execute("""
                    INSERT INTO pending_groups (user1_id, user2_id, matched_at, status)
                    VALUES (?, ?, ?, 'pending')
                """, (partner_id, new_partner_id, now))
                
                conn.commit()
                
                # Notify both about new match
                try:
                    await context.bot.send_message(
                        chat_id=partner_id,
                        text=f"🎉 *Great news! We found you a new partner!*\n\n"
                             f"Your new study partner is *{new_partner_name}*\n\n"
                             f"Admin will create your new study group soon. Keep using /checkin daily! 💪",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                
                try:
                    await context.bot.send_message(
                        chat_id=new_partner_id,
                        text=f"🎉 *You've been matched with a new study partner!*\n\n"
                             f"Your new study partner is *{partner_name}*\n\n"
                             f"Admin will create your study group soon. Keep using /checkin daily! 💪",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                
                # Notify admin about rematch
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"🔄 *REMATCH NOTIFICATION*\n\n"
                         f"User {partner_name} (ID: {partner_id}) was ghosted by {ghost_name}\n"
                         f"✓ Rematched with {new_partner_name} (ID: {new_partner_id})\n\n"
                         f"📝 New group needed for this pair!",
                    parse_mode="Markdown"
                )
                print(f"      ✅ Rematch complete - Admin notified")
            else:
                print(f"      ⏳ No available match for {partner_name} - added to waiting queue")
                # Add partner back to waiting queue if no match found
                c.execute("""
                    INSERT INTO waiting_queue (user_id, exam, study_time, language, joined_at)
                    SELECT user_id, exam, study_time, language, ? 
                    FROM users WHERE user_id = ?
                """, (datetime.utcnow().isoformat(), partner_id))
    
    conn.commit()
    conn.close()
    print(f"   ✅ Ghost detection completed - Processed {len(ghosts)} ghosts")
    logger.info(f"Ghost detection completed - Processed {len(ghosts)} ghosts")
    
# ================= MAIN FUNCTION =================
def main():
    print("=" * 50)
    print("🚀 PREPROOM ACCOUNTABILITY BOT")
    print("=" * 50)
    
    if not TOKEN:
        logger.error("❌ TOKEN not set!")
        print("ERROR: Please set TOKEN in Railway environment variables")
        return
    
    if ADMIN_USER_ID == 0:
        logger.error("❌ ADMIN_USER_ID not set!")
        print("ERROR: Please set ADMIN_USER_ID in Railway environment variables")
        return
    
    print(f"✅ Bot Token: {TOKEN[:10]}...")
    print(f"✅ Admin ID: {ADMIN_USER_ID}")
    print("=" * 50)
    
    setup_db()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CommandHandler("partner", partner_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("group_ready", group_ready))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🎯 PrepRoom Bot is running!")
    logger.info("🚀 PrepRoom Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
