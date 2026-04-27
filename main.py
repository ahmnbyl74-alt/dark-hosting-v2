import os
import subprocess
import sqlite3
import zipfile
import shutil
import sys
import json
from datetime import datetime, timedelta
from threading import Thread

# --- التثبيت التلقائي للمكتبات الأساسية للمستضيف ---
try:
    import telebot
    from telebot import types
    from flask import Flask
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyTelegramBotAPI", "flask", "requests"])
    import telebot
    from telebot import types
    from flask import Flask

# --- إعدادات الملك (تأكد من الآيدي والتوكن) ---
BOT_TOKEN = "8668457099:AAEFY6-9l0FxpB355F2NCL2LAq3UHROvRjY"
ADMIN_ID = 8249124053
BASE_DIR = "./hosted_scripts"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
running_processes = {}

# --- خادم الويب للبقاء حياً على Railway ---
app = Flask('')
@app.route('/')
def home(): return "Hosting System is Active! 🚀"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- قاعدة بيانات المشتركين ---
def init_db():
    conn = sqlite3.connect('hosting_system.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                    (user_id INTEGER PRIMARY KEY, expiry_date TEXT, is_banned INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def check_status(user_id):
    if user_id == ADMIN_ID: return "admin"
    conn = sqlite3.connect('hosting_system.db', check_same_thread=False)
    res = conn.execute('SELECT expiry_date, is_banned FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    if res and res[1] == 0:
        try:
            if datetime.now() < datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S'): return "active"
        except: pass
    return "expired"

# --- لوحة التحكم ---
def main_markup(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if uid == ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton("➕ تفعيل", callback_data="a_activate"),
            types.InlineKeyboardButton("📊 الإحصائيات", callback_data="a_stats")
        )
    markup.add(
        types.InlineKeyboardButton("🟢 حالة بوتي", callback_data="u_status"),
        types.InlineKeyboardButton("🛑 إيقاف", callback_data="u_stop")
    )
    return markup

# --- تشغيل البوت المرفوع ---
def start_user_bot(uid, target_file, user_dir):
    try:
        # تشغيل البوت داخل مجلده الخاص (حل مشكلة ملفات الـ JSON)
        process = subprocess.Popen(
            [sys.executable, target_file],
            cwd=user_dir # أهم سطر لتشغيل الملفات المساعدة
        )
        running_processes[uid] = process
        bot.send_message(uid, "✅ *تم تشغيل بوتك بنجاح!*")
    except Exception as e:
        bot.send_message(uid, f"❌ *حدث خطأ أثناء التشغيل:* {str(e)}")

# --- استقبال الملفات ---
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    uid = message.chat.id
    status = check_status(uid)
    
    if status in ["active", "admin"]:
        user_dir = os.path.join(BASE_DIR, str(uid))
        if os.path.exists(user_dir): shutil.rmtree(user_dir)
        os.makedirs(user_dir, exist_ok=True)
        
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        if message.document.file_name.endswith('.zip'):
            msg = bot.reply_to(message, "📦 *جاري فك الضغط والمعالجة...*")
            zip_path = os.path.join(user_dir, "temp.zip")
            with open(zip_path, 'wb') as f: f.write(downloaded)
            with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(user_dir)
            target = os.path.join(user_dir, "main.py")
        else:
            target = os.path.join(user_dir, "main.py")
            with open(target, 'wb') as f: f.write(downloaded)

        if os.path.exists(target):
            if uid in running_processes: running_processes[uid].terminate()
            start_user_bot(uid, target, user_dir)
        else:
            bot.send_message(uid, "❌ *خطأ:* لم يتم العثور على ملف باسم `main.py` داخل الملف المرفوع.")
    else:
        bot.send_message(uid, "🚫 *عذراً:* خدمتك غير مفعلة، تواصل مع المطور.")

# --- معالجة الأوامر والأزرار ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🛡️ *مرحباً بك في نظام الاستضافة الملكي*", reply_markup=main_markup(message.chat.id))

@bot.callback_query_handler(func=lambda call: True)
def calls(call):
    uid = call.from_user.id
    if call.data == "a_activate" and uid == ADMIN_ID:
        m = bot.send_message(uid, "📝 أرسل (ID:DAYS):")
        bot.register_next_step_handler(m, save_act)
    elif call.data == "a_stats" and uid == ADMIN_ID:
        bot.answer_callback_query(call.id, f"البوتات النشطة: {len(running_processes)}", show_alert=True)
    elif "u_status" in call.data:
        res = "🟢 بوتك يعمل الآن" if uid in running_processes else "🔴 بوتك متوقف"
        bot.answer_callback_query(call.id, res, show_alert=True)
    elif "u_stop" in call.data:
        if uid in running_processes:
            running_processes[uid].terminate()
            del running_processes[uid]
            bot.answer_callback_query(call.id, "🛑 تم إيقاف البوت")

def save_act(m):
    try:
        user_id, days = m.text.split(':')
        exp = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect('hosting_system.db')
        conn.execute('INSERT OR REPLACE INTO users (user_id, expiry_date, is_banned) VALUES (?, ?, 0)', (int(user_id), exp))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تم تفعيل {user_id}")
    except: bot.send_message(ADMIN_ID, "❌ خطأ في التنسيق")

if __name__ == "__main__":
    init_db()
    if not os.path.exists(BASE_DIR): os.makedirs(BASE_DIR)
    Thread(target=run_server, daemon=True).start()
    bot.infinity_polling()
            
