import os
import requests
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from pypdf import PdfReader

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8908467332:AAHC_ALFUDvLtdElZi6_lMm6ppA5CvjMWmA")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

app = Flask(__name__)

# راه‌اندازی اپلیکیشن تلگرام
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

def get_openai_response(prompt):
    """تابع اتصال مستقیم و واقعی به هوش مصنوعی OpenAI"""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system", 
                "content": "تو یک دستیار و مشاور حقوقی هوشمند، دقیق و متبحر به نام Saess هستی. به صورت کاملاً تخصصی، روان و پیوسته به زبان فارسی با کاربر گفتگو کن و پاسخ حقوقی بده."
            },
            {
                "role": "user", 
                "content": prompt[:4000]
            }
        ],
        "temperature": 0.5
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=35)
        print(f"OpenAI Response Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            print(f"OpenAI Error Body: {response.text}")
            return f"⚠️ خطای هوش مصنوعی (کد {response.status_code}): لطفاً کلید API یا اعتبار حساب خود را بررسی کنید."
    except Exception as e:
        print(f"OpenAI Exception: {e}")
        return f"⚠️ خطای ارتباطی با سرور هوش مصنوعی: {str(e)}"

async def start_command(update: Update, context):
    await update.message.reply_text("سلام! من **Saess** هستم، دستیار حقوقی هوشمند شما. هر سوال حقوقی یا متن و فایل PDF دارید بفرستید تا به صورت چت مستقیم پاسخ دهم.")

async def handle_incoming_message(update: Update, context):
    message = update.message
    text = message.text or message.caption or ""
    
    # خواندن فایل PDF در صورت ارسال
    if message.document and message.document.file_name.lower().endswith('.pdf'):
        await message.reply_text("📥 در حال دریافت و خواندن متن فایل PDF...")
        file = await context.bot.get_file(message.document.file_id)
        path = f"temp_{message.document.file_name}"
        await file.download_to_drive(path)
        try:
            reader = PdfReader(path)
            extracted = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    extracted += t + "\n"
            text = f"محتوای فایل PDF ارسالی:\n{extracted}" if extracted else "[فایل PDF خالی بود]"
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            text = f"[خطا در پردازش PDF: {e}]"

    if not text.strip():
        text = "سلام، لطفاً راهنمایی‌ام کنید."

    # نمایش وضعیت در حال تایپ
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    
    # دریافت پاسخ واقعی و پویا از OpenAI
    ai_reply = get_openai_response(text)
    
    # ارسال پاسخ مستقیم به کاربر در تلگرام
    await message.reply_text(ai_reply)

telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_incoming_message))

# تنظیم Event Loop برای وب‌هوک
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(telegram_app.initialize())

@app.route("/")
def index():
    return "Saess Legal Chat Bot is active!"

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, telegram_app.bot)
    loop.run_until_complete(telegram_app.process_update(update))
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    webhook_url = f"https://saess-legal-bot.onrender.com/{TELEGRAM_BOT_TOKEN}"
    loop.run_until_complete(telegram_app.bot.set_webhook(url=webhook_url))
    app.run(host="0.0.0.0", port=port)
