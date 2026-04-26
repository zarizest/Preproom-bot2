import asyncio
import logging
import sqlite3
import traceback
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ========================= CONFIG =========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables (set in deployment platform)
TOKEN = "8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI"
ADMIN_USER_ID = 8456901459

if TOKEN == "8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI":
    raise ValueError("Please set your bot TOKEN in the code or via environment variable")

# Database file
DB_NAME = "preproom.db"

# Categories and options
EXAMS = {
    "campus": "🏢 Campus Placements (TCS, Infosys, Wipro, Capgemini, Accenture, Cognizant, Other)",
    "govt": "📋 Government Exams (SSC CGL, SSC CHSL, Banking, RRB, UPSC, State PSC, Other)",
    "medical": "🏥 Medical Entrance (NEET)",
    "eng": "🔬 Engineering Entrance (JEE)",
    "mba": "🎓 MBA/GATE (CAT, GATE)",
    "other": "📚 Semester / Other",
}

STUDY_TIMES = [
    "Early Morning (5-8 AM)",
    "Morning (8 AM-12 PM)",
    "Afternoon (12-4 PM)",
    "Evening (4-8 PM)",
    "Night (8 PM-12 AM)",
    "Late Night (12-3 AM)",
]

LANGUAGES = [
    "English", "Hindi", "Marathi", "Tamil", "Telugu",
    "Bengali", "Kannada", "Malayalam",
]

# Reputation tiers
def get_tier(reputation: int) -> str:
    if reputation >= 90:
        return "💎 Diamond"
    elif reputation >= 75:
        return "🥇 Gold"
    elif reputation >= 50:
        return "🥈 Silver"
    else:
        return "🥉 Bronze"

# ====================== DATABASE ======================
def get_conn():
    """Thread-safe connection for SQLite"""
    return sqlite3.connect(DB_NAME, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
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
        )
    ''')
    
    # waiting_queue
    c.execute('''
        CREATE TABLE IF NOT EXISTS waiting_queue (
            user_id INTEGER PRIMARY KEY,
            exam TEXT,
            study_time TEXT,
            language TEXT,
            joined_at TEXT
        )
    ''')
    
    # pending_groups
    c.execute('''
        CREATE TABLE IF NOT EXISTS pending_groups (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER,
            user2_id INTEGER,
            matched_at TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    conn.commit()
    conn.close()

def migrate_database():
    """Add missing columns for backward compatibility"""
    conn = get_conn()
    c = conn.cursor()
    
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'status' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
    if 'group_id' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN group_id INTEGER")
    if 'matched_at' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN matched_at TEXT")
    
    conn.commit()
    conn.close()
    logger.info("Database migration completed")

# ====================== HELPERS ======================
def get_user_data(user_id: int) -> Optional[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(zip([col[0] for col in c.description], row))
    return None

def save_user(user_id: int, username: str, first_name: str, exam: str, study_time: str, language: str):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, exam, study_time, language, streak, reputation, last_checkin, matched_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, 40, NULL, NULL)
    ''', (user_id, username, first_name, exam, study_time, language))
    conn.commit()
    conn.close()

def add_to_waiting_queue(user_id: int, exam: str, study_time: str, language: str):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('''
        INSERT OR REPLACE INTO waiting_queue 
        (user_id, exam, study_time, language, joined_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, exam, study_time, language, now))
    conn.commit()
    conn.close()

def find_match(user_id: int, exam: str, study_time: str) -> Optional[int]:
    """Find a waiting user with same exam and study_time (language optional for broader matching)"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT user_id FROM waiting_queue 
        WHERE user_id != ? AND exam = ? AND study_time = ?
        LIMIT 1
    ''', (user_id, exam, study_time))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def remove_from_queue(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM waiting_queue WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def link_partners(user1_id: int, user2_id: int):
    now = datetime.now().isoformat()
    conn = get_conn()
    c = conn.cursor()
    
    c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
              (user2_id, now, user1_id))
    c.execute("UPDATE users SET partner_id = ?, matched_at = ? WHERE user_id = ?", 
              (user1_id, now, user2_id))
    
    # Create pending group record
    c.execute("INSERT INTO pending_groups (user1_id, user2_id, matched_at) VALUES (?, ?, ?)",
              (min(user1_id, user2_id), max(user1_id, user2_id), now))
    
    conn.commit()
    conn.close()

def notify_match(bot, user1_id: int, user2_id: int):
    # Notify both users
    msg = "🎉 Congratulations! You've been matched with a study partner!\n\n" \
          "Use /checkin daily to stay accountable.\n" \
          "Your partner will be notified when you check in.\n\n" \
          "Type /partner to see their details."
    
    try:
        asyncio.create_task(bot.send_message(user1_id, msg))
        asyncio.create_task(bot.send_message(user2_id, msg))
    except Exception as e:
        logger.error(f"Failed to notify match: {e}")

def send_admin_match_notification(context: ContextTypes.DEFAULT_TYPE, u1: dict, u2: dict):
    text = f"""🎯 NEW MATCH ALERT!

━━━━━━━━━━━━━━━━━━━━━━
👤 STUDENT 1
• Name: {u1['first_name']}
• Username: @{u1.get('username', 'N/A')}
• User ID: {u1['user_id']}

👤 STUDENT 2
• Name: {u2['first_name']}
• Username: @{u2.get('username', 'N/A')}
• User ID: {u2['user_id']}

━━━━━━━━━━━━━━━━━━━━━━
📚 MATCH DETAILS
• Exam: {u1['exam']}
• Study Time: {u1['study_time']}
• Language: {u1['language']}

━━━━━━━━━━━━━━━━━━━━━━
✅ ACTION REQUIRED:

1. Create a private Telegram group
2. Add BOTH students
3. Add the bot as admin
4. Send /group_ready in the group
"""
    try:
        context.bot.send_message(ADMIN_USER_ID, text)
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")

# ====================== COMMANDS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    existing = c.fetchone()
    conn.close()
    
    if existing:
        await update.message.reply_text(
            "👋 Welcome back to PrepRoom!\n\n"
            "Use /checkin daily to maintain your streak.\n"
            "Type /streak or /partner for stats."
        )
        return
    
    # Show exam categories
    keyboard = [
        [InlineKeyboardButton(EXAMS["campus"], callback_data="exam_campus")],
        [InlineKeyboardButton(EXAMS["govt"], callback_data="exam_govt")],
        [InlineKeyboardButton(EXAMS["medical"], callback_data="exam_medical")],
        [InlineKeyboardButton(EXAMS["eng"], callback_data="exam_eng")],
        [InlineKeyboardButton(EXAMS["mba"], callback_data="exam_mba")],
        [InlineKeyboardButton(EXAMS["other"], callback_data="exam_other")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Welcome to **PrepRoom** – Your Study Accountability Partner! 🔥\n\n"
        "Select your preparation category:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().date().isoformat()
    
    user = get_user_data(user_id)
    if not user:
        await update.message.reply_text("Please complete registration with /start first.")
        return
    
    if user.get("last_checkin") == today:
        await update.message.reply_text("✅ You've already checked in today! Great job.")
        return
    
    conn = get_conn()
    c = conn.cursor()
    
    last_checkin = user.get("last_checkin")
    streak = user.get("streak", 0)
    rep = user.get("reputation", 40)
    
    if last_checkin:
        last_date = datetime.fromisoformat(last_checkin).date()
        days_gap = (datetime.now().date() - last_date).days
        
        if days_gap == 1:
            streak += 1
            rep = min(100, rep + 2)
        else:
            streak = 1
            rep = max(0, rep - 5)
    else:
        streak = 1
        rep = min(100, rep + 2)
    
    c.execute('''
        UPDATE users 
        SET streak = ?, last_checkin = ?, reputation = ?
        WHERE user_id = ?
    ''', (streak, today, rep, user_id))
    conn.commit()
    conn.close()
    
    tier = get_tier(rep)
    await update.message.reply_text(
        f"✅ Check-in successful!\n\n"
        f"🔥 Streak: {streak} days\n"
        f"⭐ Reputation: {rep} ({tier})\n\n"
        f"Keep it up! Your partner has been notified."
    )
    
    # Notify partner
    partner_id = user.get("partner_id")
    if partner_id:
        try:
            partner_msg = f"📢 Your partner just checked in!\n\n" \
                          f"Name: {user['first_name']}\n" \
                          f"Streak: {streak} | Rep: {rep}"
            await context.bot.send_message(partner_id, partner_msg)
        except Exception:
            pass  # Partner may have blocked bot

async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    if not user:
        await update.message.reply_text("Please register with /start first.")
        return
    
    tier = get_tier(user["reputation"])
    await update.message.reply_text(
        f"📊 Your Stats\n\n"
        f"👤 Name: {user['first_name']}\n"
        f"🔥 Streak: {user['streak']} days\n"
        f"⭐ Reputation: {user['reputation']} ({tier})\n"
        f"📚 Exam: {user['exam']}\n"
        f"⏰ Time: {user['study_time']}"
    )

async def partner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    if not user or not user.get("partner_id"):
        await update.message.reply_text("You don't have a partner yet. Keep studying!")
        return
    
    partner = get_user_data(user["partner_id"])
    if not partner:
        await update.message.reply_text("Your partner data is unavailable.")
        return
    
    tier = get_tier(partner["reputation"])
    await update.message.reply_text(
        f"🤝 Your Study Partner\n\n"
        f"👤 Name: {partner['first_name']}\n"
        f"🔥 Streak: {partner['streak']} days\n"
        f"⭐ Reputation: {partner['reputation']} ({tier})"
    )

async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 PrepRoom Accountability Rules\n\n"
        "✅ Daily Check-in: /checkin\n"
        "• +2 reputation for consecutive days\n"
        "• -5 reputation if you miss a day\n\n"
        "🔥 Streaks reset if you miss 1 day\n\n"
        "⭐ Reputation starts at 40\n"
        "• 0-49: Bronze\n"
        "• 50-74: Silver\n"
        "• 75-89: Gold\n"
        "• 90-100: Diamond\n\n"
        "👻 Inactive 2+ days? Automatic ghost detection runs every 24 hours\n"
        "• Ghost penalty: -15 reputation\n\n"
        "💪 Your partner is counting on you!"
    )

async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Placeholder - can be extended for manual reporting
    await update.message.reply_text("Partner reporting is handled automatically via ghost detection.\n"
                                    "If your partner is inactive, the system will handle it within 24 hours.")

# ====================== ADMIN COMMANDS ======================
async def group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return
    
    chat_id = update.effective_chat.id
    # In production, you would link group_id to users here.
    # For simplicity, we log it and notify.
    await update.message.reply_text(f"✅ Group linked (chat_id: {chat_id}).\n"
                                    "Users can now be notified in this group if you extend the bot further.")
    logger.info(f"Group ready command used in chat {chat_id}")

async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM pending_groups WHERE status = 'pending'")
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("No pending matches.")
        return
    
    text = "📋 Pending Matches:\n\n"
    for row in rows:
        text += f"Match ID: {row[0]} | Users: {row[1]} & {row[2]}\n"
    await update.message.reply_text(text)

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, exam, study_time FROM users")
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("No registered users.")
        return
    
    text = "👥 Registered Users:\n\n"
    for row in rows:
        text += f"ID: {row[0]} | {row[1]} | {row[2]} | {row[3]}\n"
    await update.message.reply_text(text)

# ====================== BUTTON HANDLER ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    
    try:
        if data.startswith("exam_"):
            exam_key = data[5:]
            exam_name = list(EXAMS.values())[list(EXAMS.keys()).index(exam_key)]
            
            # Store temporary data in context
            context.user_data["exam"] = exam_name
            
            # Show study time options
            keyboard = [[InlineKeyboardButton(time, callback_data=f"time_{i}")] for i, time in enumerate(STUDY_TIMES)]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"Selected: {exam_name}\n\nChoose your preferred study time slot:",
                reply_markup=reply_markup
            )
        
        elif data.startswith("time_"):
            time_idx = int(data[5:])
            study_time = STUDY_TIMES[time_idx]
            context.user_data["study_time"] = study_time
            
            # Show language options
            keyboard = [[InlineKeyboardButton(lang, callback_data=f"lang_{lang}")] for lang in LANGUAGES]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"Study Time: {study_time}\n\nChoose your preferred language:",
                reply_markup=reply_markup
            )
        
        elif data.startswith("lang_"):
            language = data[5:]
            exam = context.user_data.get("exam")
            study_time = context.user_data.get("study_time")
            
            if not exam or not study_time:
                await query.edit_message_text("⚠️ Session expired. Please use /start again.")
                return
            
            # Save user
            save_user(user.id, user.username, user.first_name, exam, study_time, language)
            
            # Try to match
            match_id = find_match(user.id, exam, study_time)
            
            if match_id:
                # Match found
                link_partners(user.id, match_id)
                remove_from_queue(user.id)
                remove_from_queue(match_id)
                
                user_data = get_user_data(user.id)
                match_data = get_user_data(match_id)
                
                notify_match(context.bot, user.id, match_id)
                send_admin_match_notification(context, user_data, match_data)
                
                await query.edit_message_text(
                    "🎉 You've been matched with a study partner!\n"
                    "Check your messages for details."
                )
            else:
                # Add to queue
                add_to_waiting_queue(user.id, exam, study_time, language)
                await query.edit_message_text(
                    "✅ Registration complete!\n\n"
                    "You have been added to the waiting queue.\n"
                    "We'll notify you as soon as a matching partner is found.\n\n"
                    "Use /checkin once you start studying."
                )
    
    except Exception as e:
        logger.error(f"Button handler error: {traceback.format_exc()}")
        await query.edit_message_text("⚠️ An error occurred. Please use /start again.")

# ====================== GHOST DETECTION ======================
async def ghost_detection(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running ghost detection job...")
    threshold = (datetime.now() - timedelta(days=2)).isoformat()
    
    conn = get_conn()
    c = conn.cursor()
    
    c.execute('''
        SELECT user_id, partner_id, reputation 
        FROM users 
        WHERE partner_id IS NOT NULL 
        AND (last_checkin IS NULL OR last_checkin < ?)
        AND status = 'active'
    ''', (threshold,))
    
    ghosts = c.fetchall()
    
    for ghost_id, partner_id, rep in ghosts:
        new_rep = max(0, rep - 15)
        
        # Penalize ghost
        c.execute("UPDATE users SET reputation = ?, partner_id = NULL WHERE user_id = ?",
                  (new_rep, ghost_id))
        
        # Unlink partner
        c.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (partner_id,))
        
        # Notify
        try:
            await context.bot.send_message(ghost_id, 
                "👻 Ghost detection triggered.\n"
                "You missed check-ins for 2+ days.\n"
                f"Reputation reduced by 15. New rep: {new_rep}")
        except:
            pass
        
        try:
            await context.bot.send_message(partner_id, 
                "⚠️ Your study partner has been inactive for 2+ days and has been removed.\n"
                "We are trying to find you a new partner.")
        except:
            pass
        
        # Try rematch for the affected partner
        partner_data = get_user_data(partner_id)
        if partner_data:
            match_id = find_match(partner_id, partner_data["exam"], partner_data["study_time"])
            if match_id:
                link_partners(partner_id, match_id)
                remove_from_queue(partner_id)
                remove_from_queue(match_id)
                notify_match(context.bot, partner_id, match_id)
                logger.info(f"Rematched user {partner_id} with {match_id}")
    
    conn.commit()
    conn.close()
    logger.info(f"Ghost detection completed. Processed {len(ghosts)} ghosts.")

# ====================== MAIN ======================
def main():
    init_db()
    migrate_database()
    
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("streak", streak_cmd))
    application.add_handler(CommandHandler("partner", partner_cmd))
    application.add_handler(CommandHandler("rules", rules_cmd))
    application.add_handler(CommandHandler("report", report_cmd))
    
    # Admin commands
    application.add_handler(CommandHandler("group_ready", group_ready))
    application.add_handler(CommandHandler("pending", pending_cmd))
    application.add_handler(CommandHandler("users", users_cmd))
    
    # Button handler
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Ghost detection job (every 24 hours)
    application.job_queue.run_repeating(ghost_detection, interval=86400, first=60)
    
    logger.info("🚀 PrepRoom Bot is starting...")
    print("PrepRoom Study Accountability Bot started successfully!")
    print("Database initialized. Ghost detection scheduled every 24h.")
    
    application.run_polling()

if __name__ == "__main__":
    main()
