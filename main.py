
import os
import subprocess
import sqlite3
import zipfile
import shutil
import sys
from datetime import datetime, timedelta
from threading import Thread

# --- نظام التثبيت التلقائي للمكتبات ---
try:
    import telebot
    from telebot import types
    from flask import Flask
except ImportError:
    os.system("pip install pyTelegramBotAPI flask")
    import telebot
    from telebot import types
    from flask import Flask

# --- 🌐 خادم الويب (Railway) ---
app = Flask('')
@app.route('/')
def home(): return "Hosting System is Live! 🚀"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# --- 🛠️ الإعدادات ---
BOT_TOKEN = "8668457099:AAEFY6-9l0FxpB355F2NCL2LAq3UHROvRjY" 
ADMIN_ID = 8249124053 
BASE_DIR = "./hosted_scripts"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

running_processes = {}

# --- 🗄️ قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('hosting_system.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                    (user_id INTEGER PRIMARY KEY, expiry_date TEXT, plan TEXT, is_banned INTEGER DEFAULT 0)''')
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

# --- ⌨️ لوحات التحكم ---
def main_markup(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if uid == ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton("➕ تفعيل مستخدم", callback_data="a_activate"),
            types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="a_ban"),
            types.InlineKeyboardButton("📊 الإحصائيات", callback_data="a_stats"),
            types.InlineKeyboardButton("🚀 بوتي الشخصي", callback_data="u_status")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("🟢 حالة بوتي", callback_data="u_status"),
            types.InlineKeyboardButton("🛑 إيقاف التشغيل", callback_data="u_stop"),
            types.InlineKeyboardButton("👤 حسابي", callback_data="u_plan")
        )
    return markup

# --- 🚀 معالجة الملفات (ZIP & PY) ---
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    uid = message.chat.id
    status = check_status(uid)
    if status in ["active", "admin"]:
        file_name = message.document.file_name
        user_dir = os.path.join(BASE_DIR, str(uid))
        
        if os.path.exists(user_dir): shutil.rmtree(user_dir)
        os.makedirs(user_dir, exist_ok=True)
        
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        target_script = os.path.join(user_dir, "main.py")

        if file_name.endswith('.zip'):
            msg = bot.reply_to(message, "📦 *جاري فك الضغط...*")
            zip_p = os.path.join(user_dir, "temp.zip")
            with open(zip_p, 'wb') as f: f.write(downloaded)
            with zipfile.ZipFile(zip_p, 'r') as z: z.extractall(user_dir)
            os.remove(zip_p)
        elif file_name.endswith('.py'):
            msg = bot.reply_to(message, "🚀 *جاري الرفع...*")
            with open(target_script, 'wb') as f: f.write(downloaded)
        else:
            bot.reply_to(message, "❌ أرسل `.py` أو `.zip` فقط.")
            return

        if os.path.exists(target_script):
            if uid in running_processes:
                try: running_processes[uid].terminate()
                except: pass
            running_processes[uid] = subprocess.Popen([sys.executable, target_script])
            bot.edit_message_text("✅ *تم التشغيل بنجاح!*", uid, msg.message_id)
        else:
            bot.edit_message_text("⚠️ خطأ: تأكد من وجود ملف `main.py` داخل الـ ZIP.", uid, msg.message_id)

# --- 🎮 الأوامر والأزرار ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🛡️ *نظام الاستضافة الملكي جاهز*", reply_markup=main_markup(message.chat.id))

@bot.callback_query_handler(func=lambda call: True)
def calls(call):
    uid = call.from_user.id
    data = call.data

    if data == "a_activate" and uid == ADMIN_ID:
        m = bot.send_message(uid, "📝 أرسل الآيدي والأيام (مثال: `8249124053:30`):")
        bot.register_next_step_handler(m, save_activation)
    elif data == "a_ban" and uid == ADMIN_ID:
        m = bot.send_message(uid, "🚫 أرسل آيدي المستخدم للحظر:")
        bot.register_next_step_handler(m, save_ban)
    elif data == "a_stats" and uid == ADMIN_ID:
        bot.answer_callback_query(call.id, f"عدد البوتات النشطة: {len(running_processes)}", show_alert=True)
    elif "u_status" in data:
        res = "🟢 يعمل" if uid in running_processes else "🔴 متوقف"
        bot.answer_callback_query(call.id, res, show_alert=True)
    elif "u_stop" in data:
        if uid in running_processes:
            running_processes[uid].terminate()
            del running_processes[uid]
            bot.answer_callback_query(call.id, "🛑 تم الإيقاف")
    elif "u_plan" in data:
        conn = sqlite3.connect('hosting_system.db')
        res = conn.execute('SELECT expiry_date FROM users WHERE user_id = ?', (uid,)).fetchone()
        bot.answer_callback_query(call.id, f"ينتهي اشتراكك في: {res[0] if res else 'غير مفعل'}", show_alert=True)

# --- وظائف الإدارة ---
def save_activation(message):
    try:
        tid, days = message.text.split(':')
        expiry = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect('hosting_system.db')
        conn.execute('INSERT OR REPLACE INTO users (user_id, expiry_date, plan, is_banned) VALUES (?, ?, ?, 0)', (int(tid), expiry, 'Premium'))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تم تفعيل {tid} لمدة {days} يوم.")
    except: bot.send_message(ADMIN_ID, "❌ خطأ في التنسيق.")

def save_ban(message):
    try:
        tid = int(message.text)
        conn = sqlite3.connect('hosting_system.db')
        conn.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (tid,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"🚫 تم حظر {tid}.")
    except: bot.send_message(ADMIN_ID, "❌ خطأ.")

if __name__ == "__main__":
    init_db()
    os.makedirs(BASE_DIR, exist_ok=True)
    keep_alive()
    bot.infinity_polling()
        import os
import subprocess
import sqlite3
import zipfile
import shutil
import sys
from datetime import datetime, timedelta
from threading import Thread

# --- نظام التثبيت التلقائي للمكتبات ---
try:
    import telebot
    from telebot import types
    from flask import Flask
except ImportError:
    os.system("pip install pyTelegramBotAPI flask")
    import telebot
    from telebot import types
    from flask import Flask

# --- 🌐 خادم الويب (Railway) ---
app = Flask('')
@app.route('/')
def home(): return "Hosting System is Live! 🚀"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# --- 🛠️ الإعدادات ---
BOT_TOKEN = "8668457099:AAEFY6-9l0FxpB355F2NCL2LAq3UHROvRjY" 
ADMIN_ID = 8249124053 
BASE_DIR = "./hosted_scripts"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

running_processes = {}

# --- 🗄️ قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('hosting_system.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                    (user_id INTEGER PRIMARY KEY, expiry_date TEXT, plan TEXT, is_banned INTEGER DEFAULT 0)''')
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

# --- ⌨️ لوحات التحكم ---
def main_markup(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if uid == ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton("➕ تفعيل مستخدم", callback_data="a_activate"),
            types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="a_ban"),
            types.InlineKeyboardButton("📊 الإحصائيات", callback_data="a_stats"),
            types.InlineKeyboardButton("🚀 بوتي الشخصي", callback_data="u_status")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("🟢 حالة بوتي", callback_data="u_status"),
            types.InlineKeyboardButton("🛑 إيقاف التشغيل", callback_data="u_stop"),
            types.InlineKeyboardButton("👤 حسابي", callback_data="u_plan")
        )
    return markup

# --- 🚀 معالجة الملفات (ZIP & PY) ---
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    uid = message.chat.id
    status = check_status(uid)
    if status in ["active", "admin"]:
        file_name = message.document.file_name
        user_dir = os.path.join(BASE_DIR, str(uid))
        
        if os.path.exists(user_dir): shutil.rmtree(user_dir)
        os.makedirs(user_dir, exist_ok=True)
        
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        target_script = os.path.join(user_dir, "main.py")

        if file_name.endswith('.zip'):
            msg = bot.reply_to(message, "📦 *جاري فك الضغط...*")
            zip_p = os.path.join(user_dir, "temp.zip")
            with open(zip_p, 'wb') as f: f.write(downloaded)
            with zipfile.ZipFile(zip_p, 'r') as z: z.extractall(user_dir)
            os.remove(zip_p)
        elif file_name.endswith('.py'):
            msg = bot.reply_to(message, "🚀 *جاري الرفع...*")
            with open(target_script, 'wb') as f: f.write(downloaded)
        else:
            bot.reply_to(message, "❌ أرسل `.py` أو `.zip` فقط.")
            return

        if os.path.exists(target_script):
            if uid in running_processes:
                try: running_processes[uid].terminate()
                except: pass
            running_processes[uid] = subprocess.Popen([sys.executable, target_script])
            bot.edit_message_text("✅ *تم التشغيل بنجاح!*", uid, msg.message_id)
        else:
            bot.edit_message_text("⚠️ خطأ: تأكد من وجود ملف `main.py` داخل الـ ZIP.", uid, msg.message_id)

# --- 🎮 الأوامر والأزرار ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🛡️ *نظام الاستضافة الملكي جاهز*", reply_markup=main_markup(message.chat.id))

@bot.callback_query_handler(func=lambda call: True)
def calls(call):
    uid = call.from_user.id
    data = call.data

    if data == "a_activate" and uid == ADMIN_ID:
        m = bot.send_message(uid, "📝 أرسل الآيدي والأيام (مثال: `8249124053:30`):")
        bot.register_next_step_handler(m, save_activation)
    elif data == "a_ban" and uid == ADMIN_ID:
        m = bot.send_message(uid, "🚫 أرسل آيدي المستخدم للحظر:")
        bot.register_next_step_handler(m, save_ban)
    elif data == "a_stats" and uid == ADMIN_ID:
        bot.answer_callback_query(call.id, f"عدد البوتات النشطة: {len(running_processes)}", show_alert=True)
    elif "u_status" in data:
        res = "🟢 يعمل" if uid in running_processes else "🔴 متوقف"
        bot.answer_callback_query(call.id, res, show_alert=True)
    elif "u_stop" in data:
        if uid in running_processes:
            running_processes[uid].terminate()
            del running_processes[uid]
            bot.answer_callback_query(call.id, "🛑 تم الإيقاف")
    elif "u_plan" in data:
        conn = sqlite3.connect('hosting_system.db')
        res = conn.execute('SELECT expiry_date FROM users WHERE user_id = ?', (uid,)).fetchone()
        bot.answer_callback_query(call.id, f"ينتهي اشتراكك في: {res[0] if res else 'غير مفعل'}", show_alert=True)

# --- وظائف الإدارة ---
def save_activation(message):
    try:
        tid, days = message.text.split(':')
        expiry = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect('hosting_system.db')
        conn.execute('INSERT OR REPLACE INTO users (user_id, expiry_date, plan, is_banned) VALUES (?, ?, ?, 0)', (int(tid), expiry, 'Premium'))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تم تفعيل {tid} لمدة {days} يوم.")
    except: bot.send_message(ADMIN_ID, "❌ خطأ في التنسيق.")

def save_ban(message):
    try:
        tid = int(message.text)
        conn = sqlite3.connect('hosting_system.db')
        conn.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (tid,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"🚫 تم حظر {tid}.")
    except: bot.send_message(ADMIN_ID, "❌ خطأ.")

if __name__ == "__main__":
    init_db()
    os.makedirs(BASE_DIR, exist_ok=True)
    keep_alive()
    bot.infinity_pollin
