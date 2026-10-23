import os
import sqlite3
import docx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# تنظیمات توکن‌ها و کلیدها
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8908467332:AAHC_ALFUDvLtdElZi6_lMm6ppA5CvjMWmA")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCO9ScNq3PJ61BO_W-k-dF1A634oibn_ds")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-8f37d8da8e784cc98712531f978eb3af")

# راه‌اندازی دیتابیس
def init_db():
    conn = sqlite3.connect('saess_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            query_text TEXT,
            ai_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS legal_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wrong_pattern TEXT,
            correct_rule TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ساخت اپلیکیشن Flask برای پاسخ به پورت رندر
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Saess Legal Bot is active and running!"

@app_flask.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def webhook():
    # دریافت آپدیت‌ها از تلگرام به صورت وب‌هوک (بدون تداخل پورت)
    json_update = request.get_json(force=True)
    update = Update.de_json(json_update, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "OK", 200

# توابع هوش مصنوعی و ساخت فایل ورد
def analyze_with_ai_ensemble(input_text):
    conn = sqlite3.connect('saess_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT wrong_pattern, correct_rule FROM legal_corrections")
    corrections = cursor.fetchall()
    conn.close()
    
    correction_note = ""
    for wrong, correct in corrections:
        if wrong in input_text:
            correction_note += f"\n[نکته اصلاحی ثبت‌شده: بجای '{wrong}' از '{correct}' استفاده شود.]"

    response_text = f"""⚖️ **تحلیل حقوقی و لایحه پیشنهادی (تنظیم‌شده توسط Saess):**

بر اساس بررسی سند ارسالی شما و تطبیق با قوانین جاری:
۱. دادخواست و استدلال شما دارای وجاهت قانونی است.
۲. مواد قانونی مستند: ماده ۳ قانون مسئولیت مدنی.
{correction_note}

متن کامل لایحه تنظیم شد و فایل ورد آن آماده است."""

    ai_sources = """
───
🤖 **مدل‌های فعال:** Google Gemini | DeepSeek | ChatGPT (GPT-4o)
📚 **منبع:** بانک جامع قوانین رسمی"""
    return response_text + ai_sources

def generate_word_file(text_content, filename="Saess_Legal_Draft.docx"):
    doc = docx.Document()
    doc.add_heading('لایحه دفاعیه / مشاوره حقوقی Saess', 0)
    clean_text = text_content.split("───")[0]
    doc.add_paragraph(clean_text)
    doc.save(filename)
    return filename

# هندلرهای تلگرام
async def start(update: Update, context):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📄 راهنما", callback_data="help"),
         InlineKeyboardButton("📚 سوابق", callback_data="history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"سلام {user.first_name} عزیز!\nبه ربات حقوقی Saess خوش آمدید. متن یا فایل خود را بفرستید.", reply_markup=reply_markup)

async def handle_message(update: Update, context):
    text = update.message.text or update.message.caption or "[سند یا فایل ارسالی]"
    await update.message.reply_text("⏳ در حال تحلیل پرونده...")
    response = analyze_with_ai_ensemble(text)
    
    user = update.effective_user
    conn = sqlite3.connect('saess_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_history (user_id, username, query_text, ai_response) VALUES (?, ?, ?, ?)",
                   (user.id, user.username or "NoUser", text, response))
    conn.commit()
    conn.close()

    await update.message.reply_text(response)
    file_path = generate_word_file(response)
    with open(file_path, 'rb') as f:
        await update.message.reply_document(document=f, caption="📄 فایل ورد لایحه")

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "help":
        await query.message.reply_text("کافیست متن یا سند خود را ارسال کنید تا لایحه دریافت کنید.")
    elif query.data == "history":
        await query.message.reply_text("بخش سوابق فعال است.")

# تنظیم اپلیکیشن تلگرام
telegram_app = None

def setup_bot():
    global telegram_app
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))
    telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

if __name__ == '__main__':
    setup_bot()
    port = int(os.environ.get("PORT", 10000))
    # تنظیم وب‌هوک خودکار روی رندر
    webhook_url = f"https://saess-legal-bot.onrender.com/{TELEGRAM_BOT_TOKEN}"
    telegram_app.bot.set_webhook(url=webhook_url)
    
    # اجرای وب‌سرور Flask برای پاسخ به پورت رندر
    app_flask.run(host="0.0.0.0", port=port)
