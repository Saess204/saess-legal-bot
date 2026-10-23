import os
import sqlite3
import requests
import asyncio
from pypdf import PdfReader
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8908467332:AAHC_ALFUDvLtdElZi6_lMm6ppA5CvjMWmA")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

# دیتابیس برای ذخیره تاریخچه گفتگوها
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

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()

def get_real_ai_response(prompt_text):
    """ارسال درخواست واقعی و پویا به هوش مصنوعی OpenAI جهت چت و تحلیل حقوقی"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system", 
                    "content": "تو یک مشاور و دستیار هوشمند حقوقی متبحر به نام Saess هستی. به صورت کاملاً روان، دقیق، تخصصی و به زبان فارسی به سوالات حقوقی کاربر پاسخ بده و به صورت پیوسته با او چت کن."
                },
                {
                    "role": "user", 
                    "content": prompt_text[:4000]
                }
            ],
            "temperature": 0.5
        }
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=45)
        if response.status_code == 200:
            result = response.json()
            ai_text = result['choices'][0]['message']['content']
            return f"⚖️ **پاسخ مشاور حقوقی (Saess):**\n\n{ai_text}\n\n---\n🤖 **مدل فعال:** OpenAI GPT-4o-mini | 💬 **حالت چت فعال**"
        else:
            print(f"OpenAI API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception error: {e}")

    # پاسخ جایگزین در صورت اختطای موقت اینترنت یا API
    return f"⚖️ **پاسخ حقوقی (Saess):**\n\nمتن شما دریافت شد: «{prompt_text[:150]}...»\nلطفاً جزئیات بیشتری بفرستید تا دقیق‌تر راهنمایی‌تان کنم."

async def start(update: Update, context):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📄 راهنما", callback_data="help"),
         InlineKeyboardButton("💬 شروع گفتگو", callback_data="chat")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"سلام {user.first_name} عزیز!\n\nمن **Saess**، دستیار حقوقی هوشمند شما هستم. از این به بعد هر سوال، متن یا فایل PDF حقوقی بفرستید، مستقیماً همینجا در قالب چت و به صورت پیاپی پاسخ می‌دهم. چه کمکی از دست من برمی‌آید؟",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context):
    message = update.message
    user_text = message.text or message.caption or ""
    
    # اگر کاربر فایل PDF فرستاد، متن آن استخراج شود
    if message.document and message.document.file_name.lower().endswith('.pdf'):
        status_download = await message.reply_text("📥 در حال دریافت و خواندن فایل PDF...")
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
            user_text = f"محتوای فایل PDF ارسالی ({doc.file_name}):\n{pdf_text}" if pdf_text.strip() else f"[مستند PDF: {doc.file_name}]"
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        except Exception:
            user_text = f"[مستند PDF: {doc.file_name}]"
        await status_download.delete()

    if not user_text.strip():
        user_text = "سلام، لطفاً راهنمایی‌ام کنید."

    # ارسال پیام انتظار کوتاه
    status_msg = await message.reply_text("💬 در حال تفکر و نگارش پاسخ...")
    
    # دریافت پاسخ کاملاً پویا از هوش مصنوعی
    ai_reply = get_real_ai_response(user_text)
    
    # ذخیره در دیتابیس
    user = update.effective_user
    conn = sqlite3.connect('saess_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_history (user_id, username, query_text, ai_response) VALUES (?, ?, ?, ?)",
                   (user.id, user.username or "NoUser", user_text[:500], ai_reply))
    conn.commit()
    conn.close()

    # حذف پیام انتظار و ارسال پاسخ متنی پیاپی
    await status_msg.delete()
    await message.reply_text(ai_reply)

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "help":
        await query.message.reply_text("هر سوال حقوقی یا فایلی بفرستید، من به صورت متنی و دقیق جواب می‌دهم.")
    elif query.data == "chat":
        await query.message.reply_text("بسیار عالی، سوال یا پرونده خود را بفرستید تا گفتگو را شروع کنیم.")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

loop.run_until_complete(telegram_app.initialize())

@app_flask.route('/')
def home():
    return "Saess Legal Chat Bot is active and live!"

@app_flask.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def webhook():
    json_update = request.get_json(force=True)
    update = Update.de_json(json_update, telegram_app.bot)
    loop.run_until_complete(telegram_app.process_update(update))
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    webhook_url = f"https://saess-legal-bot.onrender.com/{TELEGRAM_BOT_TOKEN}"
    loop.run_until_complete(telegram_app.bot.set_webhook(url=webhook_url))
    app_flask.run(host="0.0.0.0", port=port)
