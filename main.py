import telebot
import os
import subprocess
import sqlite3
from datetime import datetime, timedelta
from telebot import types
from flask import Flask
from threading import Thread

# --- 🌐 إعداد خادم الويب للبقاء حياً (Flask) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Running!"

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.start()

# --- 🛠️ الإعدادات الأساسية للبوت ---
BOT_TOKEN = "8668457099:AAEFY6-9l0FxpB355F2NCL2LAq3UHROvRjY" 
ADMIN_ID = 8249124053 
BASE_DIR = "./hosted_scripts"
bot = telebot.TeleBot(BOT_TOKEN)

running_processes = {}

# --- 🗄️ قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('hosting_system.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, expiry_date TEXT, plan TEXT, is_banned INTEGER DEFAULT 0)''')
    try: cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    except: pass
    conn.commit()
    conn.close()

def check_status(user_id):
    if user_id == ADMIN_ID: return "admin"
    conn = sqlite3.connect('hosting_system.db', check_same_thread=False)
    res = conn.execute('SELECT expiry_date, is_banned FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    if res and res[1] == 0:
        if datetime.now() < datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S'): return "active"
    return "expired"

# --- ⌨️ لوحات التحكم ---
def admin_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ تفعيل/تمديد", callback_data="a_activate"),
        types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="a_ban"),
        types.InlineKeyboardButton("📢 إذاعة عامة", callback_data="a_bc"),
        types.InlineKeyboardButton("🚀 البوتات النشطة", callback_data="a_procs")
    )
    return markup

def user_markup(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🟢 حالة البوت", callback_data=f"u_status_{uid}"),
        types.InlineKeyboardButton("🛑 إيقاف", callback_data=f"u_stop_{uid}"),
        types.InlineKeyboardButton("👤 حسابي", callback_data=f"u_plan_{uid}"),
        types.InlineKeyboardButton("📖 تعليمات", callback_data=f"u_help_{uid}")
    )
    return markup

# --- 🚀 معالجة الأوامر والرسائل ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    status = check_status(uid)
    branding = "\n\n✨ **Dark Hosting Pro**"
    
    if status == "admin":
        bot.send_message(uid, f"🛡️ **لوحة المالك:**\nآيديك: `{uid}`" + branding, reply_markup=admin_markup())
    elif status == "active":
        bot.send_message(uid, f"👤 **أهلاً بك:** `{uid}`\n✅ اشتراكك فعال.\n📤 **أرسل ملف .py الآن لتشغيله.**" + branding, reply_markup=user_markup(uid))
    else:
        bot.send_message(uid, f"⚠️ **اشتراكك غير مفعل.**\nآيديك: `{uid}`" + branding)

@bot.callback_query_handler(func=lambda call: True)
def handle_clicks(call):
    uid = call.from_user.id
    data = call.data

    if uid == ADMIN_ID and data == "a_ban":
        m = bot.send_message(ADMIN_ID, "🚫 أرسل آيدي المستخدم للحظر:")
        bot.register_next_step_handler(m, process_ban)
    elif "u_help" in data:
        bot.send_message(uid, "📖 **التعليمات:**\nارسل ملف .py الخاص بك وسأقوم بتشغيله لك تلقائياً.")
    elif uid == ADMIN_ID and data == "a_activate":
        m = bot.send_message(ADMIN_ID, "📝 أرسل `الآيدي:الأيام`:")
        bot.register_next_step_handler(m, process_activation)
    elif "u_plan" in data:
        conn = sqlite3.connect('hosting_system.db')
        res = conn.execute('SELECT expiry_date FROM users WHERE user_id = ?', (uid,)).fetchone()
        bot.send_message(uid, f"👤 **حسابك ينتهي في:** `{res[0] if res else 'غير مفعّل'}`")
    elif "u_status" in data:
        st = "🟢 يعمل" if uid in running_processes else "🔴 متوقف"
        bot.answer_callback_query(call.id, st, show_alert=True)
    elif "u_stop" in data:
        if uid in running_processes:
            running_processes[uid].terminate()
            del running_processes[uid]
            bot.answer_callback_query(call.id, "🛑 تم الإيقاف.")
        else: bot.answer_callback_query(call.id, "متوقف بالفعل.")
    bot.answer_callback_query(call.id)

def process_ban(message):
    try:
        tid = int(message.text)
        conn = sqlite3.connect('hosting_system.db')
        conn.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (tid,))
        conn.commit()
        if tid in running_processes:
            running_processes[tid].terminate()
            del running_processes[tid]
        bot.send_message(ADMIN_ID, f"✅ تم حظر `{tid}`.")
    except: bot.send_message(ADMIN_ID, "❌ خطأ.")

def process_activation(message):
    try:
        tid, days = message.text.split(':')
        expiry = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect('hosting_system.db')
        conn.execute('INSERT OR REPLACE INTO users (user_id, expiry_date, plan, is_banned) VALUES (?, ?, ?, 0)', (int(tid), expiry, 'Premium'))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تم تفعيل {tid}.")
    except: bot.send_message(ADMIN_ID, "❌ خطأ.")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    uid = message.chat.id
    if check_status(uid) in ["active", "admin"]:
        if message.document.file_name.endswith('.py'):
            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)
            user_dir = f"{BASE_DIR}/{uid}"
            os.makedirs(user_dir, exist_ok=True)
            path = f"{user_dir}/main.py"
            with open(path, 'wb') as f: f.write(downloaded)
            
            if uid in running_processes: running_processes[uid].terminate()
            running_processes[uid] = subprocess.Popen(['python3', path])
            bot.reply_to(message, "🚀 **تم تشغيل ملفك تلقائياً!**")
        else: bot.reply_to(message, "❌ ملف .py فقط.")

# --- 🏁 التشغيل النهائي ---
if __name__ == "__main__":
    init_db()
    os.makedirs(BASE_DIR, exist_ok=True)
    keep_alive() # تشغيل خادم الويب في الخلفية
    print("🚀 البوت جاهز للاستضافة المجانية!")
    bot.infinity_polling()
  
