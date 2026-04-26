import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN", "8274139210:AAGylh8LVrddr62E4LnDI2UCkQ-Jb1ovspI")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "8456901459"))

# Simple database
def get_conn():
    return sqlite3.connect("preproom.db")

def setup_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        exam TEXT,
        study_time TEXT,
        language TEXT,
        streak INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS waiting_queue (
        user_id INTEGER PRIMARY KEY,
        exam TEXT,
        study_time TEXT,
        language TEXT
    )""")
    conn.commit()
    conn.close()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("TCS NQT", callback_data="exam_TCS NQT")],
        [InlineKeyboardButton("Infosys", callback_data="exam_Infosys")],
        [InlineKeyboardButton("UPSC", callback_data="exam_UPSC")],
        [InlineKeyboardButton("Banking", callback_data="exam_Banking")],
    ]
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\nSelect your exam:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    
    print(f"🔘 Clicked: {data}")
    
    # Exam selection
    if data.startswith("exam_"):
        exam = data.replace("exam_", "")
        context.user_data['exam'] = exam
        print(f"   Exam saved: {exam}")
        
        keyboard = [
            [InlineKeyboardButton("Morning", callback_data="time_Morning")],
            [InlineKeyboardButton("Evening", callback_data="time_Evening")],
            [InlineKeyboardButton("Night", callback_data="time_Night")],
        ]
        await query.edit_message_text(
            f"Exam: {exam}\nSelect study time:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Time selection
    if data.startswith("time_"):
        time_slot = data.replace("time_", "")
        context.user_data['time'] = time_slot
        print(f"   Time saved: {time_slot}")
        
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang_English")],
            [InlineKeyboardButton("Hindi", callback_data="lang_Hindi")],
        ]
        await query.edit_message_text(
            f"Exam: {context.user_data['exam']}\nTime: {time_slot}\nSelect language:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Language selection
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
            (user_id, first_name, exam, study_time, language)
            VALUES (?, ?, ?, ?, ?)""",
            (user_id, user_name, exam, study_time, language))
        conn.commit()
        conn.close()
        
        # Success message
        await query.edit_message_text(
            f"✅ Registration complete!\n\n"
            f"📚 Exam: {exam}\n"
            f"⏰ Time: {study_time}\n"
            f"🗣 Language: {language}\n\n"
            f"Use /checkin to start your streak!"
        )
        print(f"   ✅ Registration complete for {user_name}")
        return

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT streak, last_checkin FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    
    if not row:
        await update.message.reply_text("Use /start first")
        conn.close()
        return
    
    streak, last = row
    if last == today:
        await update.message.reply_text("Already checked in today!")
        conn.close()
        return
    
    streak += 1
    c.execute("UPDATE users SET streak=?, last_checkin=? WHERE user_id=?", (streak, today, user_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Checked in! Streak: {streak} days")

async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT first_name, streak FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        await update.message.reply_text(f"📊 {row[0]}, Streak: {row[1]} days")
    else:
        await update.message.reply_text("Use /start first")

def main():
    print("=" * 50)
    print("🚀 MINIMAL PREPROOM BOT")
    print("=" * 50)
    
    if not TOKEN:
        print("❌ TOKEN not set!")
        return
    
    setup_db()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Bot running! Send /start")
    app.run_polling()

if __name__ == "__main__":
    main()
