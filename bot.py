import os
import sqlite3
import logging
import traceback
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

# ================= DATABASE FIX =================
def get_conn():
    """Fixed: check_same_thread=False prevents SQLite threading issues"""
    return sqlite3.connect(DB_NAME, check_same_thread=False)

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
        status TEXT DEFAULT 'pending'
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
        await update.message.reply_text(
            f"👋 Welcome back, {user.first_name}!\n\n"
            f"📊 Use /streak to see your stats\n"
            f"✅ Use /checkin to mark today's study\n"
            f"👥 Use /partner to see your partner\n"
            f"📋 Use /rules for guidelines",
            parse_mode='Markdown'
        )
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

# ================= BUTTON HANDLER (FIXED) =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        user_id = query.from_user.id
        user_name = query.from_user.first_name
        data = query.data

        print(f"🔘 Button clicked: '{data}' by user {user_id}")

        if 'onboarding' not in context.user_data:
            context.user_data['onboarding'] = {}

        # ========== BACK FIX ==========
        if data == 'back_to_start':
            await query.message.reply_text("🔄 Restarting...")
            await start(update, context)
            return

        # ========== CATEGORY: PLACEMENTS ==========
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
            await query.edit_message_text(
                "🏢 *Campus Placements*\nSelect your target company:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        # ========== CATEGORY: GOVERNMENT ==========
        if data == 'cat_government':
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
            await query.edit_message_text(
                "📋 *Government Exams*\nSelect your target exam:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        # ========== CATEGORY: MBA/GATE ==========
        if data == 'cat_mba_gate':
            print(f"📂 Category: MBA/GATE selected by {user_id}")
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
            print(f"📂 Category: Semester selected by {user_id}")
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
        
        # ========== DIRECT EXAMS ==========
        if data in ['exam_NEET', 'exam_JEE', 'exam_CAT', 'exam_GATE', 'exam_Semester', 'exam_Other', 
                    'exam_UPSC', 'exam_Banking', 'exam_RRB', 'exam_SSC CGL', 'exam_SSC CHSL', 'exam_State PSC',
                    'exam_TCS NQT', 'exam_Infosys', 'exam_Wipro', 'exam_Capgemini', 'exam_Accenture', 'exam_Cognizant']:
            
            exam = data.replace('exam_', '')
            exam = exam.replace('_', ' ')
            context.user_data['onboarding']['exam'] = exam
            print(f"📚 Exam selected: {exam} by {user_id}")
            
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
            print(f"⏰ Time selected: {time_display} by {user_id}")
            
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
        
        # ========== LANGUAGE SELECTED (FIXED WITH TRY/CATCH) ==========
        if data.startswith('lang_'):
            print(f"🟢 Language clicked: {data} by {user_id}")

            language = data.replace('lang_', '')
            context.user_data['onboarding']['language'] = language

            exam = context.user_data['onboarding'].get('exam', 'Unknown')
            study_time = context.user_data['onboarding'].get('time', 'Unknown')

            try:
                conn = get_conn()
                c = conn.cursor()
                
                c.execute("""INSERT OR REPLACE INTO users 
                    (user_id, username, first_name, exam, study_time, language, reputation, streak)
                    VALUES (?, ?, ?, ?, ?, ?, 40, 0)""",
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
                    admin_msg = f"""🎯 *NEW MATCH ALERT!*

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
2️⃣ Add BOTH students to the group
3️⃣ Add @{context.bot.username} as admin
4️⃣ Send /group_ready in the group"""
                    
                    try:
                        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=admin_msg, parse_mode="Markdown")
                        print(f"   ✅ Admin notified")
                    except Exception as e:
                        print(f"   ❌ Admin notify failed: {e}")
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🎉 *Matched with {partner_name}!*\n\nAdmin will create your group soon.\n\nUse /checkin daily! 🔥",
                        parse_mode="Markdown"
                    )
                    await context.bot.send_message(
                        chat_id=partner_id,
                        text=f"🎉 *Matched with {user_name}!*\n\nAdmin will create your group soon.\n\nUse /checkin daily! 🔥",
                        parse_mode="Markdown"
                    )
                    
                    await query.edit_message_text(
                        f"🎉 *Matched with {partner_name}!*\n\nAdmin will create your study group soon! 🔥",
                        parse_mode="Markdown"
                    )
                    
                else:
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
                
            except Exception as e:
                print("❌ LANGUAGE BLOCK ERROR:")
                print(traceback.format_exc())
                
                await query.edit_message_text(
                    "⚠️ Error occurred while saving. Please press /start again.",
                    parse_mode="Markdown"
                )
            return
        
        # ========== UNKNOWN CALLBACK ==========
        print(f"⚠️ UNKNOWN CALLBACK: {data}")
        await query.edit_message_text(
            "❌ Something went wrong. Please use /start to begin again.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        print("❌ BUTTON HANDLER ERROR:")
        print(traceback.format_exc())
        await query.edit_message_text(
            "⚠️ An error occurred. Please use /start to begin again.",
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
• Automatic ghost detection runs every 24 hours
• Ghost penalty: -15 reputation

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
        text=f"🚨 *INACTIVITY REPORT*\n\nUser `{user_id}` reported partner `{partner_id}`\n\nInvestigate and take action.",
        parse_mode="Markdown"
    )

# ================= GHOST DETECTION =================
async def check_ghosts(context: ContextTypes.DEFAULT_TYPE):
    """Automatically detect users inactive for 2+ days and penalize them"""
    print(f"🕐 Running ghost detection at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
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
    
    if not ghosts:
        print("   ✅ No ghosts found")
        conn.close()
        return
    
    print(f"   👻 Found {len(ghosts)} ghost(s)")
    
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
                text=f"😔 *Your study partner {ghost_name} has been inactive for 2+ days.*\n\n"
                     f"We'll find you a new partner.\n\nUse /start to get rematched! 🔥",
                parse_mode="Markdown"
            )
        except:
            pass
        
        c.execute("SELECT exam, study_time FROM users WHERE user_id=?", (partner_id,))
        partner_data = c.fetchone()
        
        if partner_data:
            partner_exam, partner_time = partner_data
            
            c.execute("""
                SELECT user_id, first_name FROM waiting_queue 
                WHERE exam = ? AND study_time = ? 
                LIMIT 1
            """, (partner_exam, partner_time))
            
            new_match = c.fetchone()
            
            if new_match:
                new_partner_id, new_partner_name = new_match
                now = datetime.utcnow().isoformat()
                
                c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
                         (new_partner_id, now, partner_id))
                c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
                         (partner_id, now, new_partner_id))
                c.execute("DELETE FROM waiting_queue WHERE user_id = ?", (new_partner_id,))
                c.execute("INSERT INTO pending_groups (user1_id, user2_id, matched_at, status) VALUES (?, ?, ?, 'pending')",
                         (partner_id, new_partner_id, now))
                
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=f"🎉 *Great news! We found you a new partner: {new_partner_name}*\n\nAdmin will create your new group soon!",
                    parse_mode="Markdown"
                )
                
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"🔄 *REMATCH NOTIFICATION*\n\nUser {partner_id} rematched with {new_partner_id}\nNew group needed!",
                    parse_mode="Markdown"
                )
    
    conn.commit()
    conn.close()
    print(f"   ✅ Ghost detection completed")

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
    
    await context.bot.send_message(chat_id=u1, text="🎉 Your study group is ready! Use /checkin daily!", parse_mode="Markdown")
    await context.bot.send_message(chat_id=u2, text="🎉 Your study group is ready! Use /checkin daily!", parse_mode="Markdown")

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

# ================= ADMIN: USERS LIST =================
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ *Admin only!*", parse_mode="Markdown")
        return
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, exam, study_time, streak, reputation, partner_id FROM users LIMIT 20")
    users = c.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text("No users found", parse_mode="Markdown")
        return
    
    msg = "📊 *Registered Users:*\n\n"
    for u in users:
        msg += f"• {u[1]} (ID: {u[0]})\n  📚 {u[2]} | ⏰ {u[3]} | 🔥 {u[4]} | ⭐ {u[5]}\n  👥 Partner: {u[6] if u[6] else 'None'}\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= MAIN FUNCTION =================
def main():
    print("=" * 60)
    print("🚀 PREPROOM ACCOUNTABILITY BOT v2.0")
    print("=" * 60)
    
    if not TOKEN:
        logger.error("❌ TOKEN not set!")
        print("ERROR: Please set TOKEN in Railway environment variables")
        return
    
    if ADMIN_USER_ID == 0:
        logger.error("❌ ADMIN_USER_ID not set!")
        print("ERROR: Please set ADMIN_USER_ID in Railway environment variables")
        return
    
    print(f"\n📱 Bot Token: {TOKEN[:15]}...{TOKEN[-10:]}")
    print(f"👑 Admin ID: {ADMIN_USER_ID}")
    print(f"💾 Database: {DB_NAME}")
    print("=" * 60)
    
    try:
        setup_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return
    
    try:
        app = Application.builder().token(TOKEN).build()
        print("✅ Bot application built successfully")
    except Exception as e:
        logger.error(f"❌ Bot application build failed: {e}")
        return
    
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
    app.add_handler(CommandHandler("users", users_cmd))
    
    # Callback handler
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("\n" + "=" * 60)
    print("🎯 PREPROOM BOT IS NOW RUNNING!")
    print("=" * 60)
    print("\n📋 Commands:")
    print("   👤 User: /start, /checkin, /streak, /partner, /rules, /report")
    print("   👑 Admin: /group_ready, /pending, /users")
    print("\n✅ Ghost detection: Every 24 hours")
    print("✅ Reputation range: 0-100 (start: 40)")
    print("✅ SQLite threading fix: check_same_thread=False")
    print("=" * 60)
    
    logger.info("🚀 PrepRoom Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
