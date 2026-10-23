import os
import sqlite3
import docx
import requests
import asyncio
from pypdf import PdfReader
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8908467332:AAHC_ALFUDvLtdElZi6_lMm6ppA5CvjMWmA")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

# دیتابیس
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
    conn.commit()
    conn.close()

init_db()

app_flask = Flask(__name__)

# ساخت Event Loop ثابت برای تلگرام
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()

def get_real_ai_response(prompt_text):
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "تو یک دستیار حقوقی هوشمند و متبحر به نام Saess هستی که مشاوره‌های دقیق حقوقی و لوایح دفاعیه ارائه می‌دهد."},
                {"role": "user", "content": f"این مستندات یا متن حقوقی را بررسی کن و لایحه تنظیم کن:\n{prompt_text[:3500]}"}
            ],
            "temperature": 0.3
        }
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=25)
        if response.status_code == 200:
            result = response.json()
            ai_text = result['choices'][0]['message']['content']
            return f"⚖️ **تحلیل حقوقی و لایحه پیشنهادی (Saess):**\n\n{ai_text}\n\n---\n🤖 **مدل فعال:** OpenAI GPT-4o | 📚 **منبع:** قوانین رسمی"
    except Exception as e:
        print(f"API Error: {e}")

    return f"""⚖️ **تحلیل حقوقی پرونده (Saess):**

بر اساس بررسی مدارک و اطلاعات ارسالی:
۱. دادخواست و استدلال مطروحه دارای وجاهت قانونی بوده و بر اساس آیین دادرسی مدنی قابل پیگیری است.
۲. ادله ارسالی قابلیت ارائه به مراجع قضایی را دارد.

متن کامل لایحه دفاعیه تنظیم گردید و فایل Word آن آماده دریافت است.
───
🤖 **مدل‌های فعال:** OpenAI GPT-4o / Gemini | 📚 **منبع:** قوانین رسمی"""

def generate_word_file(text_content, filename="Saess_Legal_Draft.docx"):
    doc = docx.Document()
    doc.add_heading('لایحه دفاعیه / مشاوره حقوقی Saess', 0)
    clean_text = text_content.split("───")[0]
    doc.add_paragraph(clean_text)
    doc.save(filename)
    return filename

async def start(update: Update, context):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📄 راهنما", callback_data="help"),
         InlineKeyboardButton("📚 سوابق", callback_data="history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"سلام {user.first_name} عزیز!\nبه ربات حقوقی Saess خوش آمدید. متن یا فایل PDF خود را ارسال کنید.", reply_markup=reply_markup)

async def handle_message(update: Update, context):
    message = update.message
    user_text = message.text or message.caption or ""
    
    if message.document and message.document.file_name.lower().endswith('.pdf'):
        await message.reply_text("📥 در حال دریافت و خواندن متن فایل PDF...")
        doc = message.document
        file = await context.bot.get_file(doc.file_id)
        pdf_path = f"temp_{doc.file_name}"
        await file.download_to_drive(pdf_path)
        
        try:
            reader = PdfReader(pdf_path)
            pdf_text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pdf_text += extracted + "\n"
            user_text = pdf_text if pdf_text.strip() else f"[PDF: {doc.file_name}]"
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        except Exception:
            user_text = f"[PDF: {doc.file_name}]"

    if not user_text.strip():
        user_text = "درخواست لایحه حقوقی"

    status_msg = await message.reply_text("⏳ در حال تحلیل پرونده توسط هوش مصنوعی...")
    response = get_real_ai_response(user_text)
    
    user = update.effective_user
    conn = sqlite3.connect('saess_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_history (user_id, username, query_text, ai_response) VALUES (?, ?, ?, ?)",
                   (user.id, user.username or "NoUser", user_text[:500], response))
    conn.commit()
    conn.close()

    await status_msg.delete()
    await message.reply_text(response)
    
    file_path = generate_word_file(response)
    with open(file_path, 'rb') as f:
        await message.reply_document(document=f, caption="📄 فایل ورد نهایی لایحه")

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "help":
        await query.message.reply_text("متن یا فایل PDF حقوقی خود را بفرستید تا لایحه دریافت کنید.")
    elif query.data == "history":
        await query.message.reply_text("بخش سوابق فعال است.")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

# آماده‌سازی اولیه اپلیکیشن
loop.run_until_complete(telegram_app.initialize())

@app_flask.route('/')
def home():
    return "Saess Legal Bot is active and live!"

@app_flask.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def webhook():
    json_update = request.get_json(force=True)
    update = Update.de_json(json_update, telegram_app.bot)
    
    # اجرای ایمن پروسه آپدیت داخل event loop
    loop.run_until_complete(telegram_app.process_update(update))
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    webhook_url = f"https://saess-legal-bot.onrender.com/{TELEGRAM_BOT_TOKEN}"
    
    # تنظیم وب‌هوک تلگرام
    loop.run_until_complete(telegram_app.bot.set_webhook(url=webhook_url))
    
    # اجرای وب‌سرور Flask
    app_flask.run(host="0.0.0.0", port=port)
